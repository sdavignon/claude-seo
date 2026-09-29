# Codex installation and execution

Use Python 3.10 or later. From this checkout run:

```powershell
python scripts/install_codex.py
```

This installs 33 unique skills into `~/.agents/skills`, including optional
extension instructions. It does not connect providers or install dependencies.
Use `--dest "C:/Users/you/.codex/skills"` to maintain an existing installation
there instead. Choose one discovery location to avoid duplicate skills. A new
Codex session may be needed to discover the changes.

Existing destinations are refused by default. `--replace` moves all replaced
skills, including local edits, into a timestamped sibling backup before publishing
the new files. Failed publication rolls back. Unrelated skills are untouched.
Review the backup before discarding anything. Run from the verified checkout;
this installer never downloads or executes an upstream install script.

Supporting scripts, data, schema, role prompts and extension references live
under the installed `seo` directory. Nested extension SKILL.md files are excluded
so every skill has exactly one discoverable entry. Generated instructions contain
actual absolute paths and a quoted Python command matching the installation OS.
Rerun the installer if Python or the installation location moves. Original Claude
skill files, plugin hooks and installers remain compatible and unchanged.

## Runtime and explicit validation

In the repository:

```powershell
python scripts/codex-seo.py doctor --json
python scripts/codex-seo.py setup --skip-browser
python scripts/codex-seo.py run seo_updates.py --json
python scripts/codex-seo.py validate-schema "path with spaces/page.html"
```

Use the absolute commands in installed skills after installation. `doctor` is
read-only and exits 3 if setup is required. `setup` explicitly creates the existing
managed virtual environment and downloads Python dependencies; omit `--skip-browser`
to also install Chromium. These commands use Python directly as a launcher; bundled
analysis still runs through the managed runtime. Windows does not need Bash.
No runtime installation happens during skill installation, diagnosis or failed runs.

Claude PostToolUse hooks are not registered with Codex. Run `validate-schema`
explicitly after relevant edits, inspect diagnostics, and record results. Its
standard-library validator returns 0 for no detected issue, 1 for warnings and 2
for blocking findings or invalid input. It is a heuristic, not full schema validation.

## Tools, delegation and integrations

Discover current Codex tools and their schemas; Claude tool names are not automatic
aliases. A full audit permits at most three concurrent child agents, subject to
the host limit and instructions. Read each installed role prompt, give a bounded
scope, collect evidence, and run later batches as needed. No recursive delegation.
Perform the same roles inline if the host does not support or allow delegation.
This does not create recurring automations or register Claude named agents.

Use available authenticated GSC Wizard tools only after successful access and
property checks. A payment-required response means unavailable; do not infer access
from tool discovery. Direct Google API scripts are an independent option with their
own credentials and property permissions. GSC access does not imply GA4 access.
Use native image tools when appropriate; OmniEditor article images must retain the
brand-aware OmniEditor generator and persistent Base44 media URL workflow.

Optional provider skills do not prove account, API or free-plan availability.
Verify current entitlements before calls. No automatic paid calls or billing trials.
Never include credentials in generated instructions, reports or repository files.

For direct Google read-only authorization use a desktop OAuth client downloaded
to a secure local file, then run:

```powershell
python scripts/codex-seo.py auth-google --creds "C:/secure/client.json"
```

This fixed launcher action needs no managed runtime and requests only Search Console
read-only and Analytics read-only permissions. It accepts only `--creds` with an
existing local file. It cannot dispatch arbitrary scripts or broaden the scopes.
The local callback at `http://localhost:8085` validates a fresh state and uses S256
PKCE. Its server suppresses callback logs. Keep the process running until completion;
never paste the callback URL, code or token into chat. The auth flow itself uses the
Python standard library; subsequent API requests require the managed dependencies.
The legacy default scopes remain for explicitly requested write workflows. A saved
token is not evidence that every service or property is accessible: verify each
requested read. When OAuth is unavailable, authorized Browser access to Search
Console reports provides a manual read-only fallback.
