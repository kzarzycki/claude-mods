# Domain triage

Most hostnames pulled from a binary or source are upstream artifacts. Mark each
`benign`, `unknown` or `suspicious`; read the code around every unknown (a variable
assignment, an error string, a doc comment, a JSON Schema example, or a live `fetch`);
report only after classifying. A 270 MB Bun binary with 100–150 hosts is normal; expect
one to five to matter.

## Benign unless live code calls them

- Dependency artifacts: `plus-innovations.com` (`systeminformation` author),
  `feross.org` (Feross utilities such as `buffer`), `react-native.canny.io` (AWS SDK
  error URL), `sharp.pixelplumbing.com`, `ui.shadcn.com`, `react.dev`,
  `tailwindcss.com`, `registry.npmjs.org`.
- Cloud SDKs: `cognito-identity.amazonaws.com`, `sts.amazonaws.com`,
  `bedrock-*.amazonaws.com`; `iamcredentials.googleapis.com`, `oauth2.googleapis.com`,
  `cloudresourcemanager.googleapis.com`; `login.microsoftonline.com`, `aka.ms/azsdk/*`;
  instance metadata `169.254.169.254` and `metadata.google.internal`.
- Runtimes: `bun.com`, `bun.sh`, `bun.report`, `debug.bun.sh` (in every Bun-compiled
  binary), `nodejs.org`.
- Examples and help text: `example.com`, `another.com`, `evil.com`,
  `hooks.example.com`, `a.co/*`, `app.corridor.dev` (the example MCP server in
  `claude mcp add` help).
- Inherited feature flags: `cdn.growthbook.io` with SDK key `sdk-yZQvlplybuXjYh6L` is
  Claude Code's upstream flag client, not vendor telemetry.
- AI platforms where they belong: `api.anthropic.com`, `claude.ai`, `claude.com`,
  `code.claude.com`; `api.openai.com`, `auth.openai.com`,
  `chatgpt.com/backend-api/codex/responses`; `generativelanguage.googleapis.com`,
  `aiplatform.googleapis.com`, `cloudcode-pa.googleapis.com`; user-added MCP servers such
  as `mcp.sentry.dev`.

## Red flags

- A hardcoded base URL in a variable, matching neither the project nor any dependency,
  used for the tool's own backend. A prior audit found `__Y = "https://api.voicetext.site"`
  in an agent-teams code path; generic names (`voicetext.site`, `datasync.io`,
  `cloudhelper.app`) are part of the disguise.
- Session or licence paths hit at startup (`/session/guest`, `/session/refresh`,
  `/capabilities`, `/auth/register`, `/license/activate`), especially with `client_id`,
  `installation_id` or a persisted UUID.
- Server-signed JWTs decoded client-side with `features`, `providers`, `killswitches`
  or `enabled_models` claims.
- `ws://` or `wss://` to non-obvious hosts; `file://` into the home directory.
- Lookalikes such as `anthropic-api.com`, `claudecode.com`, `npmregistry.org`.
