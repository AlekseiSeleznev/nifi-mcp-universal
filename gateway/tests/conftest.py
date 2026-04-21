"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import requests

from gateway.nifi.client import NiFiClient
from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry


@pytest.fixture()
def mock_session():
    """A requests.Session mock with a working .ok response."""
    session = MagicMock(spec=requests.Session)
    session.verify = True
    session.cert = None
    session.headers = {}
    return session


@pytest.fixture()
def nifi_client(mock_session):
    """NiFiClient backed by a mock session."""
    return NiFiClient("https://nifi.example.com/nifi-api", mock_session, timeout_seconds=5)


@pytest.fixture()
def registry():
    """Fresh ConnectionRegistry (not the module singleton)."""
    return ConnectionRegistry()


@pytest.fixture()
def sample_conn():
    return ConnectionInfo(
        name="test",
        url="https://nifi.example.com/nifi-api",
        auth_method="none",
        readonly=True,
        verify_ssl=True,
    )
