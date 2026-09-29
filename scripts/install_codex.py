#!/usr/bin/env python3
"""Install an independent Codex skill tree without modifying Claude sources.

Standard library only. No packages, credentials, hooks, or MCP servers are installed.
Existing skills require --replace and are retained in a timestamped sibling backup.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def remove_tree(path: Path) -> None:
    # Windows/OneDrive may preserve read-only directory attributes from copytree.
    def retry(function, name, error):
        os.chmod(name, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(name)
    shutil.rmtree(path, onerror=retry)


def sources(root: Path) -> dict[str, Path]:
    found = {p.parent.name: p.parent for p in sorted((root / "skills").glob("*/SKILL.md"))}
    # Extension sources are authoritative for the two intentional core mirrors.
    for path in sorted((root / "extensions").glob("*/skills/*/SKILL.md")):
        found[path.parent.name] = path.parent
    if not found or "seo" not in found:
        raise ValueError("Source repository does not contain the SEO skills")
    return found


def quote(value: Path, windows: bool) -> str:
    return "'" + str(value).replace("'", "''" if windows else "'\"'\"'") + "'"


def adapt(text: str, target: Path, python: Path, windows: bool) -> str:
    shared = target / "seo"
    # Claude setup recipes mutate a different harness. Do not ship them as Codex
    # actions, including recipes embedded in extension reference documents.
    text = re.sub(r'^.*(?:claude mcp|~\/\.claude\/settings\.json|\$HOME/\.claude/settings\.json|(?:bash |\.\/|/)(?:install|uninstall)\.(?:sh|ps1)).*$',
                  'Codex: use docs/CODEX.md for setup; discover current connector tools and obtain any required account access. Do not run a Claude extension installer.',
                  text, flags=re.M)
    text = re.sub(r'\*\*Runtime:\*\*.*?(?=\nComprehensive SEO analysis)',
                  '**Runtime:** Use the generated absolute Python launcher below. It dispatches analysis through the managed runtime; no Bash or Claude variable expansion is used.\n',
                  text, flags=re.S)
    command = ("& " if windows else "") + quote(python, windows) + " " + quote(shared / "scripts/codex-seo.py", windows)
    for runner in ('"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"', '"$HOME/.claude/skills/seo/scripts/claude-seo"', '"~/.claude/skills/seo/scripts/claude-seo"', './scripts/claude-seo'):
        text = text.replace(runner, command)
    text = re.sub(r'\$\{CLAUDE_PLUGIN_ROOT\}/extensions/[^/]+/skills/([^/]+)/', lambda m: (target / m[1]).as_posix() + '/', text)
    text = text.replace('${CLAUDE_PLUGIN_ROOT}/skills/', target.as_posix() + '/')
    text = text.replace('${CLAUDE_PLUGIN_ROOT}', shared.as_posix())
    for prefix in ('$HOME/.claude/skills/', '~/.claude/skills/'):
        text = text.replace(prefix, target.as_posix() + '/')
    for prefix in ('$HOME/.claude/agents', '~/.claude/agents'):
        text = text.replace(prefix, (shared / 'agents').as_posix())
    text = text.replace('verify `SERANKING_API_KEY` is present in `~/.claude/settings.json` under `env.`. If absent, tell the user to run the installer.',
                        'verify the current SE Ranking connector is authenticated and entitled. If unavailable, report setup required; never read or display secret values.')
    text = text.replace('check `~/.claude/settings.json` has `env.PROFOUND_API_KEY`.',
                        'verify the current Profound connector is authenticated and entitled without reading or displaying secret values.')
    return text


def guidance(target: Path) -> str:
    return f"""\n## Codex execution contract\n
These Codex-specific instructions govern execution of the upstream recipes below.
Invoke this skill by name or natural language; Claude slash commands are examples,
not registered Codex commands. Use the absolute generated launcher commands.
The launcher uses Python to dispatch through the managed runtime; Windows needs
no Bash. Remaining upstream shell snippets express recipes, not executable Windows
commands: translate environment assignments and shell syntax to the active shell,
or use structured subprocess arguments. Never execute Bash examples in PowerShell.
`doctor --json` is read-only; `setup` explicitly installs dependencies
and optionally Chromium. A missing runtime is not permission for automatic setup.

Discover the actual tools and schemas available in this Codex session before use.
Read/Write/Edit/Bash/Task/WebFetch names below describe capabilities, not aliases.
Use available file tools, shell, browser and connector tools as appropriate.
For a full audit this skill permits bounded delegation when the harness permits:
read the applicable role under `{(target / 'seo/agents').as_posix()}`, then use the
available spawn_agent tool with that role's scope and evidence requirements.
Run at most three independent child agents concurrently (or the lower session
limit), collect their results, and assign remaining work in later batches.
Do not spawn recursively. If delegation is unavailable or disallowed, perform
each role inline and preserve the same evidence and scope. Do not assume a named
Claude agent has been registered. Never start recurring jobs without a user request.

Prefer an available authenticated GSC Wizard connector for supported Search Console
reads; first verify its property access, schema and entitlement. A payment-required
response means unavailable; use independently authorized direct Google APIs when
configured, without bypassing a provider paywall. It does not prove GA4 or other
Google API access. If connector entitlement fails and local OAuth is unavailable, use authorized
read-only Search Console reports in the connected Browser as a manual fallback,
clearly identifying their date range, property and coverage. Prefer native image tools
for suitable tasks; OmniEditor articles must use OmniEditor's brand-aware generator and returned
persistent Base44 URL. Do not substitute logos. Connector presence does not prove
entitlement, credentials or free quota. No automatic paid calls, purchases, trials
requiring billing, or external submissions. Report unsupported integrations plainly.

Claude hooks are not registered in Codex. After schema edits explicitly run the
launcher with `validate-schema <file>`; exit 0 means no detected issue, 1 warnings,
2 blocking findings or invalid input. Review diagnostics; this is not a complete
Schema.org validator. Report actual checks separately from edits and deployment.
\n"""


def install(root: Path, target: Path, replace: bool = False, python: Path | None = None) -> dict:
    raw_target = target.expanduser()
    if raw_target.is_symlink():
        raise ValueError("Refusing a symlinked skill destination")
    root, target = root.resolve(), target.expanduser().resolve()
    python = (python or Path(sys.executable)).resolve()
    skill_sources = sources(root)
    if target == root or root.is_relative_to(target) or target.is_relative_to(root):
        raise ValueError("Install skills outside the source repository")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or any((target / name).is_symlink() for name in skill_sources):
        raise ValueError("Refusing to replace symlinked skill destinations")
    existing = [name for name in skill_sources if (target / name).exists()]
    if existing and not replace:
        raise FileExistsError("Existing skills preserved; use --replace to back them up: " + ', '.join(existing))
    stage = Path(tempfile.mkdtemp(prefix=".seo-codex-stage-", dir=target.parent))
    backup = target.parent / ("seo-codex-backup-" + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    moved, published = [], []
    try:
        for name, source in skill_sources.items():
            shutil.copytree(source, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shared = stage / 'seo'
        for name in ('scripts', 'schema', 'data', 'agents', 'hooks', 'extensions', 'docs'):
            if (root / name).is_dir():
                shutil.copytree(root / name, shared / name, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('SKILL.md', '__pycache__', '*.pyc', '.venv', 'node_modules'))
        for name in ('requirements.txt', 'pyproject.toml', 'LICENSE'):
            shutil.copy2(root / name, shared / name)
        for path in stage.rglob('*.md'):
            text = adapt(path.read_text(encoding='utf-8'), target, python, os.name == 'nt')
            if path.name == 'SKILL.md':
                # Preserve only portable identity fields; body remains upstream.
                match = re.match(r'\A---\s*\n(.*?)\n---\s*\n', text, re.S)
                if not match:
                    raise ValueError(f"Missing frontmatter in {path.name}")
                name = re.search(r'^name:.*$', match[1], re.M)
                description = re.search(r'^description:.*(?:\n[ \t]+.*)*', match[1], re.M)
                if not name or not description:
                    raise ValueError('Skill missing name or description')
                text = '---\n' + name[0] + '\n' + description[0] + '\n---\n' + guidance(target) + text[match.end():]
            path.write_text(text, encoding='utf-8')
        manifest = {'skills': sorted(skill_sources), 'count': len(skill_sources), 'runtime_setup': False}
        (shared / 'codex-install.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        target.mkdir(exist_ok=True)
        if existing:
            backup.mkdir()
        for name in skill_sources:
            if name in existing:
                (target / name).rename(backup / name)
                moved.append(name)
            (stage / name).rename(target / name)
            published.append(name)
        manifest['backup'] = str(backup) if existing else None
        return manifest
    except Exception:
        for name in reversed(published):
            remove_tree(target / name)
        for name in reversed(moved):
            (backup / name).rename(target / name)
        raise
    finally:
        remove_tree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(ROOT, args.dest, args.replace), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f'Codex installation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
