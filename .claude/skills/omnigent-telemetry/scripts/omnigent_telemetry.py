#!/usr/bin/env python3
"""Omnigent spend, tokens and anomaly flags over the last N days, from three sources.

    python3 scripts/omnigent_telemetry.py [--days N] [--json] [--html PATH] [--db-container NAME]

- The Omnigent API (any logged-in host): ``GET /v1/usage?days=N`` gives spend today, over 7 and 30
  days, and each top-level session tree's cost by model. Login and token refresh are
  ``orchestrating-agents``' ``omnigent_agent.py``.
- The server's Postgres, through ``docker exec <container> psql`` (default container
  ``omnigent-postgres-1``): daily cost, tokens by model, each root tree's sub-agents, nested
  Codex sub-agents, compactions and items inherited from a fork, live subscriptions and
  scheduled-task runs. Unreachable, the report names the sections it left out and why.
- Local Codex rollout files: the newest rate-limit snapshot.

The window is the last N UTC days, today included, as ``/v1/usage`` counts its 7 and 30 days.
Token and per-model numbers are each session's lifetime totals, for the sessions of the trees
active in the window. Exit 0 whenever a report is printed. Stdlib only; ``session_usage``
blobs decode with ``zstandard`` when importable, else the ``zstd`` CLI.
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ left in the sibling skill's folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orchestrating-agents" / "scripts"))
from omnigent_agent import Fail, Omnigent

DB_CONTAINER = "omnigent-postgres-1"
# /v1/usage builds its window on request: slower than the 30 s of any other call
USAGE_SECONDS = 180.0
ROLLOUTS = "~/.omnigent/codex-native/*/codex-home/sessions/*/*/*/rollout-*.jsonl"
ROLLOUT_FILES = 15  # newest rollouts scanned for a populated rate-limit snapshot
TOP_TREES = 15  # trees in the text and HTML tables; --json has all

# Enum codes from Omnigent's omnigent/db/enum_codecs.py.
COMPACTION = 6  # conversation_items.type
FAILED_SESSION = 4  # omnigent_conversation_metadata.live_status
RUN_SUCCEEDED, RUN_FAILED, RUN_SKIPPED = 3, 4, 5  # scheduled_task_runs.status
LIVE = {1: "idle", 2: "running", 3: "waiting", 4: "failed"}

# Flag thresholds: a flag fires at its threshold and stays quiet below it.
SUBAGENTS = 25  # sub-agents in one root tree
NESTED_CODEX = 6  # Codex's own sub-agents (sub_agent_name 'Codex') in one tree
VERIFIER_PASS = 4  # an early warning, below engineering-loop's default cap of 5
INHERITED_ITEMS = 500  # items a session created in the window inherited from a fork
SUBSCRIBERS = 2  # sessions one target wakes when it ends a turn
CRON_FAILURES = 3  # failed runs of one scheduled task in the window
SIDEBAR_SESSIONS = 10  # unarchived top-level sessions scheduled runs created
PASS = re.compile(r"(?:-p|\bpass\s*)(\d+)\b", re.IGNORECASE)

DB_SECTIONS = (
    "daily cost",
    "tokens by model",
    "session trees' sub-agents, nested Codex sub-agents, compactions and forked items",
    "subscriptions",
    "scheduled tasks",
    "anomaly flags",
)


# --- sources ---------------------------------------------------------------------------------


def psql(container: str, sql: str) -> list:
    """One query's rows as a JSON list, so no row is split on a delimiter."""
    out = subprocess.run(
        ["docker", "exec", container, "psql", "-U", "omnigent", "-d", "omnigent", "-At"]
        + ["-v", "ON_ERROR_STOP=1", "-c", f"SELECT coalesce(json_agg(t), '[]') FROM ({sql}) t"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if out.returncode:
        raise Fail(out.stderr.strip() or f"psql exited {out.returncode}")
    return json.loads(out.stdout)


def unzstd(blob: bytes) -> bytes:
    try:
        import zstandard
    except ImportError:
        return subprocess.run(
            ["zstd", "-d", "-q", "-c"], input=blob, capture_output=True, check=True
        ).stdout
    return zstandard.ZstdDecompressor().decompressobj().decompress(blob)


def decode_usage(hex_blob: str | None) -> dict:
    """A ``session_usage`` blob: NUL, a codec byte (0 raw, 1 zstd), then JSON; or legacy plain JSON."""
    if not hex_blob:
        return {}
    raw = bytes.fromhex(hex_blob)
    if raw[:1] != b"\x00":
        return json.loads(raw)
    return json.loads(unzstd(raw[2:]) if raw[1:2] == b"\x01" else raw[2:])


def fetch_db(container: str, since: int) -> dict:
    trees = f"SELECT root_conversation_id FROM conversations WHERE updated_at >= {since}"
    db = {
        "sessions": psql(
            container,
            f"""SELECT encode(c.id, 'hex') AS id, encode(c.parent_conversation_id, 'hex') AS parent_id,
              encode(c.root_conversation_id, 'hex') AS root_id, c.title, c.created_at, c.updated_at,
              c.archived, c.next_position AS items, a.name AS agent, h.name AS host,
              m.workspace, m.live_status, m.sub_agent_name,
              encode(m.session_usage, 'hex') AS usage,
              (SELECT count(*) FROM conversation_items i WHERE i.conversation_id = c.id
                 AND i.workspace_id = c.workspace_id AND i.type = {COMPACTION}) AS compactions,
              (SELECT count(*) FROM conversation_items i WHERE i.conversation_id = c.id
                 AND i.workspace_id = c.workspace_id AND i.created_at < c.created_at) AS inherited
            FROM conversations c
            JOIN omnigent_conversation_metadata m ON m.id = c.id AND m.workspace_id = c.workspace_id
            LEFT JOIN agents a ON a.id = c.agent_id AND a.workspace_id = c.workspace_id
            LEFT JOIN hosts h ON h.host_id = m.host_id
            WHERE c.root_conversation_id IN ({trees})""",
        ),
        "subscriptions": psql(
            container,
            """SELECT encode(s.subscriber_id, 'hex') AS subscriber_id, cs.title AS subscriber_title,
              encode(s.target_id, 'hex') AS target_id, ct.title AS target_title
            FROM session_subscriptions s
            LEFT JOIN conversations cs ON cs.id = s.subscriber_id AND cs.workspace_id = s.workspace_id
            LEFT JOIN conversations ct ON ct.id = s.target_id AND ct.workspace_id = s.workspace_id""",
        ),
        "tasks": psql(
            container,
            f"""SELECT encode(t.id, 'hex') AS id, t.name, t.state, t.workspace,
              count(r.id) AS runs,
              count(r.id) FILTER (WHERE r.status = {RUN_SUCCEEDED}
                AND coalesce(m.live_status, 0) <> {FAILED_SESSION}) AS ok,
              count(r.id) FILTER (WHERE r.status = {RUN_FAILED}
                OR m.live_status = {FAILED_SESSION}) AS failed,
              count(r.id) FILTER (WHERE r.status = {RUN_SKIPPED}) AS skipped,
              (array_agg(r.error_code ORDER BY r.scheduled_at DESC)
                FILTER (WHERE r.error_code IS NOT NULL))[1] AS last_error
            FROM scheduled_tasks t
            LEFT JOIN scheduled_task_runs r ON r.scheduled_task_id = t.id
              AND r.workspace_id = t.workspace_id AND r.scheduled_at >= {since}
            LEFT JOIN omnigent_conversation_metadata m ON m.id = r.conversation_id
              AND m.workspace_id = r.workspace_id
            GROUP BY t.id, t.name, t.state, t.workspace""",
        ),
        "sidebar": psql(
            container,
            """SELECT count(*) AS unarchived, count(*) FILTER (WHERE EXISTS (
                SELECT 1 FROM scheduled_task_runs r
                WHERE r.conversation_id = c.id AND r.workspace_id = c.workspace_id)) AS from_tasks
            FROM conversations c WHERE NOT c.archived AND c.parent_conversation_id IS NULL""",
        )[0],
    }
    for s in db["sessions"]:  # ponytail: one decode per blob; batch them if this gets slow
        s["usage"] = decode_usage(s["usage"])
    # Last, and the API right after it (main): today's row grows by the second while sessions run.
    db["daily"] = psql(
        container,
        "SELECT day_utc AS day, sum(cost_usd) AS cost_usd FROM user_daily_cost"
        f" WHERE day_utc >= '{day(since)}' GROUP BY day_utc ORDER BY day_utc",
    )
    return db


def codex_rate_limits(pattern: str = ROLLOUTS) -> dict | None:
    """The newest populated ``payload.rate_limits`` in this host's Codex rollouts."""
    files = sorted(glob.glob(os.path.expanduser(pattern)), key=os.path.getmtime, reverse=True)
    for path in files[:ROLLOUT_FILES]:
        try:
            lines = Path(path).read_bytes().splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if b'"rate_limits"' not in line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            limits = (obj.get("payload") or {}).get("rate_limits") or {}
            windows = [limits[k] for k in ("primary", "secondary") if limits.get(k)]
            if windows:
                return {"timestamp": obj.get("timestamp"), "file": path, "windows": windows}
    return None


# --- analysis: pure functions over plain rows ------------------------------------------------


def day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def window_start(days: int, now: float) -> int:
    """UTC midnight of the first of the last ``days`` days, today included."""
    today = datetime.fromtimestamp(now, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int((today - timedelta(days=days - 1)).timestamp())


def cost(usage: dict) -> float:
    return float(usage.get("total_cost_usd") or 0.0)


def verifier_pass(title: str) -> int:
    return max((int(n) for n in PASS.findall(title or "")), default=0)


def models_of(sessions: list[dict]) -> list[dict]:
    rows: dict[str, dict] = defaultdict(
        lambda: dict.fromkeys(
            ("sessions", "cost_usd", "input_tokens", "cache_read_tokens", "output_tokens"), 0
        )
    )
    for s in sessions:
        for name, u in (s["usage"].get("by_model") or {}).items():
            row = rows[name]
            row["sessions"] += 1
            row["cost_usd"] += cost(u)
            row["input_tokens"] += u.get("input_tokens") or 0
            row["cache_read_tokens"] += u.get("cache_read_input_tokens") or 0
            row["output_tokens"] += u.get("output_tokens") or 0
    return sorted(
        ({"model": m, **r} for m, r in rows.items()),
        key=lambda r: (-r["cost_usd"], -r["cache_read_tokens"]),
    )


def trees_of(api_sessions: list[dict], sessions: list[dict] | None, since: int) -> list[dict]:
    """One row per root tree: cost from the API (summed over its subtree), counts from the DB."""
    by_root: dict[str, list[dict]] = defaultdict(list)
    for s in sessions or []:
        by_root[s["root_id"] or s["id"]].append(s)
    api = {s["id"]: s for s in api_sessions if (s.get("updated_at") or 0) >= since}
    rows = []
    for rid in set(api) | set(by_root):
        members = by_root.get(rid, [])
        root = next((s for s in members if s["id"] == rid), {})
        a = api.get(rid, {})
        children = [s for s in members if s["id"] != rid]
        row = {
            "id": rid,
            "title": a.get("title") or root.get("title") or "",
            "updated_at": max([a.get("updated_at") or 0] + [s["updated_at"] for s in members]),
            "cost_usd": a["cost_usd"] if a else sum(cost(s["usage"]) for s in members),
            "models": a.get("models") or {},
        }
        if sessions is not None:
            row.update(
                host=root.get("host") or "",
                agent=root.get("agent") or "",
                workspace=root.get("workspace") or "",
                status=LIVE.get(root.get("live_status"), ""),
                root_cost_usd=cost(root.get("usage") or {}),
                subagents=len(children),
                nested_codex=sum(1 for s in children if s.get("sub_agent_name") == "Codex"),
                items=sum(s["items"] or 0 for s in members),
                inherited=root.get("inherited") or 0,
                compactions=sum(s["compactions"] for s in members),
                tokens=sum(s["usage"].get("total_tokens") or 0 for s in members),
                late_verifiers=sorted(
                    s["title"] for s in children if verifier_pass(s["title"]) >= VERIFIER_PASS
                ),
            )
        rows.append(row)
    return sorted(rows, key=lambda r: -r["cost_usd"])


def flags_of(db: dict, trees: list[dict], since: int) -> list[str]:
    flags = []
    for t in trees:
        name = f"{t['id'][:8]} '{t['title'][:40]}'"
        if t["subagents"] >= SUBAGENTS or t["nested_codex"] >= NESTED_CODEX:
            flags.append(
                f"SUBAGENT_EXPLOSION {name}: {t['subagents']} sub-agents, {t['nested_codex']}"
                f" nested Codex, ${t['cost_usd']:.2f}"
            )
        if t["late_verifiers"]:
            flags.append(
                f"VERIFIER_CHURN {name}: {len(t['late_verifiers'])} verifier sessions at pass"
                f" >= {VERIFIER_PASS} ({', '.join(t['late_verifiers'][:3])})"
            )
    for s in db["sessions"]:
        if s["created_at"] >= since and (s["inherited"] or 0) >= INHERITED_ITEMS:
            flags.append(
                f"FORK_BLOAT {s['id'][:8]} '{(s['title'] or '')[:40]}': started with"
                f" {s['inherited']} inherited items, {(s['items'] or 0) - s['inherited']} its own"
            )
    by_target: dict[str, list[dict]] = defaultdict(list)
    for e in db["subscriptions"]:
        by_target[e["target_id"]].append(e)
    for target, edges in by_target.items():
        if len(edges) >= SUBSCRIBERS:
            subs = ", ".join(
                f"{e['subscriber_id'][:8]} '{(e['subscriber_title'] or '')[:24]}'" for e in edges
            )
            flags.append(
                f"SUBSCRIPTION_AMPLIFICATION {target[:8]} '{(edges[0]['target_title'] or '')[:40]}'"
                f" wakes {len(edges)} subscribers: {subs}"
            )
    for t in db["tasks"]:
        if t["failed"] >= CRON_FAILURES:
            flags.append(
                f"CRON_FAIL_LOOP {t['id'][:8]} '{t['name']}': {t['failed']}/{t['runs']} runs failed"
                f" (last error {t['last_error'] or 'none recorded'})"
            )
    side = db["sidebar"]
    if side["from_tasks"] >= SIDEBAR_SESSIONS:
        flags.append(
            f"SIDEBAR_NOISE {side['from_tasks']} of {side['unarchived']} unarchived top-level"
            " sessions were created by scheduled-task runs"
        )
    return flags


def build(
    usage: dict | None,
    db: dict | None,
    rate_limits: dict | None,
    days: int,
    now: float,
    left_out: dict[str, str] | None = None,
) -> dict:
    """The report from whatever sources answered; ``left_out`` maps each missing section to why."""
    since = window_start(days, now)
    left_out = dict(left_out or {})
    api_sessions = (usage or {}).get("sessions") or []
    trees = trees_of(api_sessions, db["sessions"] if db else None, since)
    if db:
        models = models_of(db["sessions"])
    else:  # cost only: the API carries no tokens
        totals: dict[str, float] = defaultdict(float)
        for t in trees:
            for m, c in t["models"].items():
                totals[m] += c
        models = [
            {"model": m, "cost_usd": c} for m, c in sorted(totals.items(), key=lambda x: -x[1])
        ]
    if rate_limits is None:
        left_out.setdefault("Codex rate limits", "no Codex rollout with a rate-limit snapshot here")
    return {
        "window": {"days": days, "from": day(since), "to": day(now), "generated": now},
        "spend": None
        if usage is None
        else {k: usage.get(k) for k in ("cost_today", "cost_last_7d", "cost_last_30d")},
        "daily": db["daily"] if db else None,
        "rate_limits": rate_limits,
        "models": models,
        "trees": trees,
        "tasks": sorted(db["tasks"], key=lambda t: (-t["failed"], -t["runs"])) if db else None,
        "subscriptions": len(db["subscriptions"]) if db else None,
        "sidebar": db["sidebar"] if db else None,
        "flags": flags_of(db, trees, since) if db else None,
        "left_out": left_out,
    }


# --- rendering -------------------------------------------------------------------------------


def usd(x: float | None) -> str:
    return "-" if x is None else f"${x:,.2f}"


def mtok(n: float) -> str:
    return f"{n / 1e6:,.1f}M"


def window_name(w: dict) -> str:
    return {300: "5h", 10080: "weekly"}.get(w.get("window_minutes"), f"{w.get('window_minutes')}m")


def resets(w: dict) -> str:
    at = w.get("resets_at")
    return datetime.fromtimestamp(at, tz=timezone.utc).strftime("%m-%d %H:%M UTC") if at else "?"


def model_cells(m: dict) -> list[str]:
    if "sessions" not in m:
        return [m["model"], "", usd(m["cost_usd"]), "", "", ""]
    return [
        m["model"],
        str(m["sessions"]),
        usd(m["cost_usd"]),
        mtok(m["input_tokens"]),
        mtok(m["cache_read_tokens"]),
        mtok(m["output_tokens"]),
    ]


MODEL_HEAD = ["model", "sessions", "cost", "uncached in", "cache read", "output"]
TREE_HEAD = ["root", "updated", "host", "harness", "sub-agents (nested Codex)", "items (forked)"]
TREE_HEAD += ["compactions", "cost (root)", "title"]
TASK_HEAD = ["task", "name", "runs", "ok", "failed", "skipped", "last error", "workspace"]


def tree_cells(t: dict) -> list[str]:
    updated = datetime.fromtimestamp(t["updated_at"], tz=timezone.utc).strftime("%m-%d %H:%M")
    if "subagents" not in t:
        return [t["id"][:8], updated, "", "", "", "", "", usd(t["cost_usd"]), t["title"]]
    return [
        t["id"][:8],
        updated,
        t["host"],
        t["agent"],
        f"{t['subagents']} ({t['nested_codex']})",
        f"{t['items']} ({t['inherited']})",
        str(t["compactions"]),
        f"{usd(t['cost_usd'])} ({usd(t['root_cost_usd'])})",
        t["title"],
    ]


def task_cells(t: dict) -> list[str]:
    cells = [t["id"][:8], t["name"], t["runs"], t["ok"], t["failed"], t["skipped"]]
    return [str(c) for c in cells] + [t["last_error"] or "", t["workspace"] or ""]


def daily_total(r: dict) -> float:
    return sum(d["cost_usd"] for d in r["daily"])


def text(r: dict) -> str:
    w = r["window"]
    out = [f"Omnigent telemetry, last {w['days']} days ({w['from']} to {w['to']} UTC)", ""]
    if r["spend"]:
        s = r["spend"]
        out.append(
            f"Spend (API): today {usd(s['cost_today'])}, 7 days {usd(s['cost_last_7d'])},"
            f" 30 days {usd(s['cost_last_30d'])}"
        )
    if r["daily"] is not None:
        out.append(f"Daily cost (DB), window total {usd(daily_total(r))}:")
        out += [f"  {d['day']}  {usd(d['cost_usd']):>10}" for d in r["daily"]]
    if r["rate_limits"]:
        rl = r["rate_limits"]
        windows = ", ".join(
            f"{window_name(x)} {x.get('used_percent')}% used, resets {resets(x)}"
            for x in rl["windows"]
        )
        out.append(f"Codex rate limits ({rl['timestamp']}): {windows}")

    def table(title: str, head: list[str], rows: list[list[str]]) -> None:
        out.extend(["", title, "  " + " | ".join(head)])
        out.extend("  " + " | ".join(row) for row in rows)

    table("Models", MODEL_HEAD, [model_cells(m) for m in r["models"]])
    table(
        f"Session trees, top {TOP_TREES} of {len(r['trees'])} by cost",
        TREE_HEAD,
        [tree_cells(t) for t in r["trees"][:TOP_TREES]],
    )
    if r["tasks"] is not None:
        table("Scheduled tasks", TASK_HEAD, [task_cells(t) for t in r["tasks"] if t["runs"]])
        out.append(
            f"\nLive subscriptions: {r['subscriptions']}. Unarchived top-level sessions:"
            f" {r['sidebar']['unarchived']}, {r['sidebar']['from_tasks']} from scheduled runs."
        )
    if r["flags"] is not None:
        out.append(f"\nFlags ({len(r['flags'])}):")
        out += [f"  {f}" for f in r["flags"]] or ["  none"]
    if r["left_out"]:
        out.append("\nLeft out:")
        out += [f"  {k}: {why}" for k, why in r["left_out"].items()]
    return "\n".join(out) + "\n"


CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--bar:#3a6ea5;--flag:#a5481d}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#9a9993;
--line:#2f2f2c;--bar:#6c9fd6;--flag:#e08a5a}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;
padding:24px 16px;max-width:1200px;margin-inline:auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:28px 0 8px}
.muted{color:var(--muted)}.cards{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
.card{border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:130px}
.card b{display:block;font-size:20px;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600}td:last-child{white-space:normal}
.bars{display:grid;grid-template-columns:auto 1fr auto;gap:4px 10px;align-items:center}
.bar{height:14px;background:var(--bar);border-radius:3px;min-width:1px}
ul.flags li{color:var(--flag);margin:4px 0}
"""


def page(r: dict) -> str:
    """One self-contained page: inline CSS, no script, nothing fetched."""
    e = html.escape
    w = r["window"]
    cards = []
    if r["spend"]:
        s = r["spend"]
        cards += [("Today", s["cost_today"]), ("7 days", s["cost_last_7d"])]
        cards.append(("30 days", s["cost_last_30d"]))
    if r["daily"] is not None:
        cards.append((f"{w['days']}-day window (DB)", daily_total(r)))
    body = [
        f"<h1>Omnigent telemetry, last {w['days']} days</h1>",
        f"<div class=muted>{e(w['from'])} to {e(w['to'])} UTC</div>",
        "<div class=cards>"
        + "".join(
            f"<div class=card><span class=muted>{e(k)}</span><b>{usd(v)}</b></div>"
            for k, v in cards
        )
        + "</div>",
    ]
    if r["rate_limits"]:
        rl = r["rate_limits"]
        windows = ", ".join(
            f"{window_name(x)} {x.get('used_percent')}% used, resets {resets(x)}"
            for x in rl["windows"]
        )
        body.append(f"<p>Codex rate limits ({e(str(rl['timestamp']))}): {e(windows)}</p>")
    if r["daily"]:
        top = max(d["cost_usd"] for d in r["daily"]) or 1
        body.append("<h2>Daily spend</h2><div class=bars>")
        for d in r["daily"]:
            body.append(
                f"<span>{e(d['day'])}</span><div class=bar style='width:{100 * d['cost_usd'] / top:.1f}%'>"
                f"</div><span>{usd(d['cost_usd'])}</span>"
            )
        body.append("</div>")

    def table(title: str, head: list[str], rows: list[list[str]]) -> None:
        body.append(f"<h2>{e(title)}</h2><div class=scroll><table><tr>")
        body.append("".join(f"<th>{e(h)}</th>" for h in head) + "</tr>")
        body.extend("<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in rows)
        body.append("</table></div>")

    if r["flags"] is not None:
        body.append(f"<h2>Flags ({len(r['flags'])})</h2><ul class=flags>")
        body += [f"<li>{e(f)}</li>" for f in r["flags"]] or ["<li>none</li>"]
        body.append("</ul>")
    table("Models", MODEL_HEAD, [model_cells(m) for m in r["models"]])
    table(
        f"Session trees, top {TOP_TREES} of {len(r['trees'])} by cost",
        TREE_HEAD,
        [tree_cells(t) for t in r["trees"][:TOP_TREES]],
    )
    if r["tasks"] is not None:
        table("Scheduled tasks", TASK_HEAD, [task_cells(t) for t in r["tasks"] if t["runs"]])
    if r["left_out"]:
        body.append("<h2>Left out</h2><ul>")
        body += [f"<li>{e(k)}: {e(why)}</li>" for k, why in r["left_out"].items()]
        body.append("</ul>")
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Omnigent telemetry</title><style>{CSS}</style></head><body>"
        + "\n".join(body)
        + "</body></html>\n"
    )


# --- entry -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--days", type=int, default=7, help="last N UTC days, today included (7)")
    p.add_argument(
        "--server",
        default="",
        help="Omnigent server URL; default: this session's, else the one login",
    )
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--html", metavar="PATH", help="also write a self-contained HTML page")
    p.add_argument(
        "--db-container", default=DB_CONTAINER, help=f"Postgres container ({DB_CONTAINER})"
    )
    args = p.parse_args(argv)
    if args.days < 1:
        p.error("--days must be at least 1")
    now = time.time()
    left_out: dict[str, str] = {}
    usage = db = None
    try:  # first: its daily cost and the API's are read under a second apart
        db = fetch_db(args.db_container, window_start(args.days, now))
    except (Fail, OSError, ValueError, subprocess.SubprocessError) as e:
        reason = f"Postgres via `docker exec {args.db_container}` unreachable: {str(e)[:200]}"
        left_out.update(dict.fromkeys(DB_SECTIONS, reason))
    try:
        usage = Omnigent(args.server).call(
            "GET", f"/v1/usage?days={args.days}", timeout=USAGE_SECONDS
        )
    except (Fail, OSError, ValueError) as e:
        left_out["spend and session-tree cost (API)"] = str(e)
    r = build(usage, db, codex_rate_limits(), args.days, now, left_out)
    if args.html:
        Path(args.html).write_text(page(r))
    print(json.dumps(r, indent=2) if args.json else text(r), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
