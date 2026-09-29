"""Scope, state and PKCE security without contacting Google or opening a browser."""
import base64
import hashlib
import importlib.util
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('google_auth', Path(__file__).resolve().parents[1] / 'scripts/google_auth.py')
auth = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auth)


@pytest.mark.parametrize('readonly', [True, False])
def test_scope_and_pkce(readonly):
    url, state, verifier = auth._oauth_authorization({'client_id': 'test', 'client_secret': 'SECRET'}, readonly)
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    expected = auth.READ_ONLY_OAUTH_SCOPES if readonly else auth.OAUTH_SCOPES
    assert set(params['scope'][0].split()) == set(expected.split())
    assert params['state'] == [state]
    assert params['code_challenge_method'] == ['S256']
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert params['code_challenge'] == [challenge]
    assert verifier not in url and 'SECRET' not in url
    assert auth._oauth_authorization({'client_id': 'test'}, readonly)[1] != state


@pytest.mark.parametrize('path', ['/?code=secret', '/?state=wrong&code=secret',
                                 '/?state=correct&state=wrong&code=secret',
                                 '/?state=correct&code=secret&error=denied',
                                 '/favicon.ico?state=correct&code=secret'])
def test_reject_unbound_callback(path):
    assert auth._oauth_callback_code(path, 'correct') is None


def test_valid_callback():
    assert auth._oauth_callback_code('/?state=correct&code=secret', 'correct') == 'secret'


def test_exchange_sends_verifier_without_logging_secrets(monkeypatch, capsys):
    captured = {}
    def exchange(request):
        captured.update(urllib.parse.parse_qs(request.data.decode()))
        raise RuntimeError('CALLBACK_SECRET TOKEN_SECRET')
    monkeypatch.setattr(urllib.request, 'urlopen', exchange)
    with pytest.raises(SystemExit):
        auth._exchange_code({'client_id': 'test', 'client_secret': 'CLIENT_SECRET'}, 'CALLBACK_SECRET', code_verifier='PKCE_SECRET')
    output = capsys.readouterr()
    assert captured['code_verifier'] == ['PKCE_SECRET']
    for secret in ('CALLBACK_SECRET', 'TOKEN_SECRET', 'CLIENT_SECRET', 'PKCE_SECRET'):
        assert secret not in output.out + output.err


@pytest.mark.parametrize('scope,indexing,gsc', [
    (auth.READ_ONLY_OAUTH_SCOPES, False, True),
    (auth.OAUTH_SCOPES, True, True),
    (None, False, False),
    ('', False, False),
    (auth.SCOPES['ga4'], False, False),
])
def test_diagnostics_respect_scope_metadata(monkeypatch, scope, indexing, gsc):
    monkeypatch.setattr(auth, 'load_config', lambda: {'ga4_property_id': 'test'})
    monkeypatch.setattr(auth, '_load_oauth_token', lambda: {
        'access_token': 'secret', 'expires_at': 9999999999, 'scope': scope})
    assert auth.check_credentials('indexing')['available'] == indexing
    assert auth.check_credentials('gsc')['available'] == gsc
    assert auth.check_credentials('gsc')['verified'] is False
    tier = auth.detect_tier()
    assert ('Indexing API' in tier['capabilities']) == indexing
    assert ('Search Console' in tier['capabilities']) == gsc
    assert 'PageSpeed Insights' not in tier['capabilities']
    assert tier['verified'] is False


def test_expired_scope_is_not_available(monkeypatch):
    monkeypatch.setattr(auth, 'load_config', lambda: {})
    monkeypatch.setattr(auth, '_load_oauth_token', lambda: {
        'access_token': 'secret', 'expires_at': 0, 'scope': auth.READ_ONLY_OAUTH_SCOPES})
    assert not auth.check_credentials('gsc')['available']
