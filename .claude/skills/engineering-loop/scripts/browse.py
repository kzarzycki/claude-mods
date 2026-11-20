#!/usr/bin/env -S uv run -q --script
# /// script
# dependencies = ["playwright==1.63.0"]
# ///
"""Render a web UI in headless Chromium and save a screenshot.

    uv run scripts/browse.py <url> --out <png> [--omnigent] [--do <file.py>] [--size 1440x900] [--full-page] [--wait-until load]

--do runs a Python file with Playwright's `page` in scope after the page loads and before
the screenshot: click, hover, type, wait for a selector, assert. An exception there exits
non-zero, so the file doubles as a scripted check; the screenshot is still saved.

--omnigent signs the browser in to an Omnigent server with the CLI's login: the token in
~/.omnigent/auth_tokens.json, keyed by the URL's origin, is the same JWT the web UI keeps in
its session cookie. A token within a minute of expiry is renewed through the CLI's own
refresh_stored_token, which rotates the refresh token under the CLI's lock. The token is
never printed.

Console errors and HTTP responses of 400 and up go to stderr, since a failing request is a
finding even when the page looks right. Playwright is pinned to 1.63.0, whose Chromium build
(1243) is the one in ~/.cache/ms-playwright, so nothing is downloaded.

In a sandbox that mounts the home directory read-only (a Codex session), uv can't lock its
cache: set UV_CACHE_DIR to a writable directory such as /tmp/uv-cache. A token refresh also
writes ~/.omnigent, so with an expired token run it outside such a sandbox.
"""

import argparse
import json
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

TOKENS = Path.home() / ".omnigent/auth_tokens.json"
REFRESH = "import sys; from omnigent.cli_auth import refresh_stored_token as r; sys.exit(r(sys.argv[1]) is None)"


def omnigent_token(origin: str) -> str:
    entry = json.loads(TOKENS.read_text()).get(origin) if TOKENS.exists() else None
    if not entry:
        sys.exit(f"no Omnigent login for {origin} in {TOKENS}: run `omnigent login {origin}`")
    if entry.get("expires_at", 0) - time.time() < 60:
        cli = shutil.which("omnigent")
        # The CLI's interpreter (its shebang) has omnigent importable.
        python = Path(cli).read_text().splitlines()[0].removeprefix("#!") if cli else None
        if not python or subprocess.run([python, "-c", REFRESH, origin], check=False).returncode:
            sys.exit(
                f"Omnigent login for {origin} expired and did not refresh: the refresh writes "
                f"{TOKENS.parent}, so run outside a sandbox that can't, else `omnigent login {origin}`"
            )
        entry = json.loads(TOKENS.read_text())[origin]
    return entry["token"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help="screenshot path (.png)")
    ap.add_argument("--omnigent", action="store_true", help="sign in with the Omnigent CLI's login")
    ap.add_argument(
        "--do", type=Path, help="Python file run with `page` in scope before the screenshot"
    )
    ap.add_argument("--size", default="1440x900", help="viewport WIDTHxHEIGHT")
    ap.add_argument("--full-page", action="store_true")
    ap.add_argument(
        "--wait-until",
        default="networkidle",
        choices=["load", "domcontentloaded", "networkidle"],
        help="load for an app that long-polls and never goes idle; then wait in --do",
    )
    args = ap.parse_args()
    width, height = map(int, args.size.split("x"))
    from playwright.sync_api import sync_playwright  # here, so the token logic imports without it

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": height})
        if args.omnigent:
            url = urlsplit(args.url)
            origin = f"{url.scheme}://{url.netloc}"
            https = url.scheme == "https"
            # omnigent/server/accounts_config.py: session_cookie_name, __Host- prefixed on HTTPS.
            context.add_cookies(
                [
                    {
                        "name": "__Host-ap_session" if https else "ap_session",
                        "value": omnigent_token(origin),
                        "url": origin + "/",
                        "secure": https,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                ]
            )
        page = context.new_page()
        page.on(
            "console", lambda m: m.type == "error" and print(f"console: {m.text}", file=sys.stderr)
        )
        page.on(
            "requestfailed",
            lambda r: print(f"failed: {r.method} {r.url} {r.failure}", file=sys.stderr),
        )
        page.on(
            "response",
            lambda r: (
                r.status >= 400
                and print(f"http {r.status}: {r.request.method} {r.url}", file=sys.stderr)
            ),
        )
        page.goto(args.url, wait_until=args.wait_until)
        try:
            if args.do:
                runpy.run_path(str(args.do), init_globals={"page": page})
        finally:  # a failed --do still leaves the page it failed on
            page.screenshot(path=args.out, full_page=args.full_page)
        browser.close()
    print(args.out)


if __name__ == "__main__":
    main()
