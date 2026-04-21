"""Tests for gateway.nifi.auth — KnoxAuthFactory session building."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, mock_open
import requests

from gateway.nifi.auth import KnoxAuthFactory


def _factory(**kwargs) -> KnoxAuthFactory:
    defaults = dict(
        gateway_url="https://gateway.example.com",
        token=None,
        cookie=None,
        user=None,
        password=None,
        token_endpoint=None,
        passcode_token=None,
        verify=True,
    )
    defaults.update(kwargs)
    return KnoxAuthFactory(**defaults)


class TestNoAuth:
    def test_build_session_returns_session(self):
        factory = _factory()
        session = factory.build_session()
        assert isinstance(session, requests.Session)

    def test_verify_ssl_true(self):
        factory = _factory(verify=True)
        session = factory.build_session()
        assert session.verify is True

    def test_verify_ssl_false(self):
        factory = _factory(verify=False)
        session = factory.build_session()
        assert session.verify is False

    def test_empty_gateway_url(self):
        factory = _factory(gateway_url="")
        session = factory.build_session()
        assert isinstance(session, requests.Session)


class TestCookieAuth:
    def test_cookie_set_in_header(self):
        factory = _factory(cookie="hadoop-jwt=mytoken")
        session = factory.build_session()
        assert session.headers["Cookie"] == "hadoop-jwt=mytoken"

    def test_cookie_takes_priority_over_token(self):
        factory = _factory(cookie="my-cookie", token="my-token")
        session = factory.build_session()
        # cookie takes priority
        assert session.headers["Cookie"] == "my-cookie"


class TestKnoxTokenAuth:
    def test_knox_token_set_as_cookie(self):
        factory = _factory(token="my-jwt-token")
        session = factory.build_session()
        assert "hadoop-jwt=my-jwt-token" in session.headers["Cookie"]

    def test_token_sent_without_bearer(self):
        factory = _factory(token="my-jwt-token")
        session = factory.build_session()
        # Knox tokens go as cookies, not Authorization header
        assert "Authorization" not in session.headers


class TestPasscodeAuth:
    def test_passcode_without_endpoint_uses_header(self):
        factory = _factory(
            passcode_token="passcode123",
            gateway_url="",  # no gateway, so token_endpoint is None
            token_endpoint=None,
        )
        factory.token_endpoint = None  # override
        session = factory.build_session()
        assert session.headers.get("X-Knox-Passcode") == "passcode123"

    def test_passcode_with_endpoint_exchanges_for_jwt(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": "exchanged-jwt"}

        factory = _factory(
            passcode_token="passcode123",
            gateway_url="https://gateway.example.com",
        )
        factory.token_endpoint = "https://gateway.example.com/knoxtoken/api/v1/token"

        with patch("requests.get", return_value=mock_resp):
            session = factory.build_session()

        assert session.headers.get("Authorization") == "Bearer exchanged-jwt"


class TestBasicAuth:
    def test_basic_auth_fetches_knox_token(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": "jwt-from-exchange"}

        factory = _factory(
            user="admin",
            password="secret",
            gateway_url="https://gateway.example.com",
        )

        with patch("requests.get", return_value=mock_resp):
            session = factory.build_session()

        assert session.headers.get("Authorization") == "Bearer jwt-from-exchange"

    def test_basic_auth_without_endpoint_skips_token(self):
        """Without a token_endpoint, basic auth falls through to plain session."""
        factory = _factory(user="admin", password="secret", gateway_url="")
        factory.token_endpoint = None
        session = factory.build_session()
        assert "Authorization" not in session.headers

    def test_fetch_knox_token_text_fallback(self):
        """When response is plain text JWT, use text directly."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("not json")
        mock_resp.text = "a.b.c"  # JWT-like

        factory = _factory(
            user="admin",
            password="secret",
            gateway_url="https://gateway.example.com",
        )

        with patch("requests.get", return_value=mock_resp):
            token = factory._fetch_knox_token()

        assert token == "a.b.c"


class TestP12CertResolve:
    def test_resolve_client_cert_returns_none_without_certs(self):
        factory = _factory()
        assert factory._resolve_client_cert() is None

    def test_resolve_client_cert_pem(self, tmp_path):
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        cert.write_bytes(b"CERT")
        key.write_bytes(b"KEY")
        factory = _factory(
            client_cert=str(cert),
            client_key=str(key),
        )
        result = factory._resolve_client_cert()
        assert result == (str(cert), str(key))

    def test_cleanup_tmp_files_noop_when_empty(self):
        factory = _factory()
        # Must not raise
        factory._cleanup_tmp_files()


class TestGatewayUrlNormalization:
    def test_trailing_slash_stripped(self):
        factory = _factory(gateway_url="https://gateway.example.com/")
        assert factory.gateway_url == "https://gateway.example.com"

    def test_token_endpoint_auto_built(self):
        factory = _factory(gateway_url="https://gateway.example.com")
        assert factory.token_endpoint is not None
        assert "knoxtoken" in factory.token_endpoint
