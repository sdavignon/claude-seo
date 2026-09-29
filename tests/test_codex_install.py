"""Codex layout and launcher regressions, with no network or package installation."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('install_codex', ROOT / 'scripts/install_codex.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


@pytest.fixture
def installed(tmp_path):
    target = tmp_path / 'path with spaces' / 'skills'
    result = installer.install(ROOT, target)
    return target, result


def test_unique_skills_and_support(installed):
    target, result = installed
    assert result['count'] == 33
    assert len(list(target.rglob('SKILL.md'))) == 33
    assert len(set(result['skills'])) == 33
    for name in result['skills']:
        text = (target / name / 'SKILL.md').read_text(encoding='utf-8')
        assert 'Codex execution contract' in text
        assert '${CLAUDE_PLUGIN_ROOT}' not in text
        assert '~/.claude/' not in text
        assert '$HOME/.claude/' not in text
        assert 'claude mcp' not in text
        assert 'bash install.sh' not in text
    assert (target / 'seo/extensions/banana/scripts/generate.py').is_file()
    assert (target / 'seo/requirements.txt').is_file()
    assert (target / 'seo/agents/seo-technical.md').is_file()
    assert (target / 'seo/references/cwv-thresholds.md').is_file()
    assert (target / 'seo-agentic/references/lighthouse-agentic-category.md').is_file()


def test_preserve_existing_and_backup(installed):
    target, _ = installed
    marker = target / 'seo/user-edit.txt'
    marker.write_text('user work')
    with pytest.raises(FileExistsError):
        installer.install(ROOT, target)
    assert marker.read_text() == 'user work'
    result = installer.install(ROOT, target, replace=True)
    assert (Path(result['backup']) / 'seo/user-edit.txt').read_text() == 'user work'
    assert not marker.exists()


def test_doctor_is_read_only_and_no_bash(installed):
    target, _ = installed
    launcher = target / 'seo/scripts/codex-seo.py'
    result = subprocess.run([sys.executable, str(launcher), 'doctor', '--json'], capture_output=True, text=True)
    assert result.returncode == 3
    status = json.loads(result.stdout)
    assert not status['ready']
    assert not (target / 'seo/.venv').exists()
    result = subprocess.run([sys.executable, str(launcher), 'run', '../bad.py'], capture_output=True, text=True)
    assert result.returncode == 2


def test_shell_quoting_and_reference_translation(tmp_path):
    target = tmp_path / "User's skills"
    python = tmp_path / "Python's directory/python.exe"
    source = '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" doctor\n${CLAUDE_PLUGIN_ROOT}/skills/seo/references/test.md'
    windows = installer.adapt(source, target, python, True)
    assert windows.startswith("& '")
    assert "Python''s directory" in windows
    assert (target / 'seo/references/test.md').as_posix() in windows
    posix = installer.adapt(source, target, python, False)
    assert "'\"'\"'" in posix


def test_claude_setup_is_not_a_codex_action(tmp_path):
    text = 'claude mcp add provider\nbash ./extensions/foo/install.sh\nRead ~/.claude/settings.json\n'
    result = installer.adapt(text, tmp_path / 'skills', Path(sys.executable), True)
    assert 'claude mcp' not in result
    assert '.claude/settings.json' not in result
    assert '/install.sh' not in result


def test_reject_root_symlink_before_resolve(tmp_path, monkeypatch):
    target = tmp_path / 'linked-skills'
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda path: path == target or original(path))
    with pytest.raises(ValueError, match='symlinked'):
        installer.install(ROOT, target)
    assert not target.exists()


def test_rollback_after_publish_failure(installed, monkeypatch):
    target, _ = installed
    marker = target / 'seo/user-edit.txt'
    marker.write_text('preserve')
    rename = Path.rename

    def fail_stage(self, destination):
        if '.seo-codex-stage-' in str(self) and self.name == 'seo-audit':
            raise OSError('simulated publish failure')
        return rename(self, destination)

    monkeypatch.setattr(Path, 'rename', fail_stage)
    with pytest.raises(OSError) as error:
        installer.install(ROOT, target, replace=True)
    assert str(error.value) == 'simulated publish failure'
    assert marker.read_text() == 'preserve'
    assert len(list(target.glob('*/SKILL.md'))) == 33


def test_validator_requires_file(installed):
    target, _ = installed
    result = subprocess.run([sys.executable, str(target / 'seo/scripts/codex-seo.py'),
                             'validate-schema', str(target / 'missing.html')], capture_output=True)
    assert result.returncode == 2


def test_auth_google_is_fixed_readonly_argument_list(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('codex_launcher', ROOT / 'scripts/codex-seo.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    client = tmp_path / 'client with spaces.json'
    client.write_text('{}')
    calls = []
    monkeypatch.setattr(launcher.subprocess, 'call', lambda args: calls.append(args) or 0)
    assert launcher.main(['auth-google', '--creds', str(client)]) == 0
    assert calls[0] == [sys.executable, str(ROOT / 'scripts/google_auth.py'),
                        '--auth', '--read-only', '--creds', str(client)]
    assert launcher.main(['auth-google', '--creds', str(client), '--exchange']) == 2
    assert len(calls) == 1
