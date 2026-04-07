from __future__ import annotations

import atexit
import base64
import os
import tempfile
from typing import Optional, Tuple

import requests


class KnoxAuthFactory:
	def __init__(
		self,
		gateway_url: str,
		token: Optional[str],
		cookie: Optional[str],
		user: Optional[str],
		password: Optional[str],
		token_endpoint: Optional[str],
		passcode_token: Optional[str],
		verify: bool | str,
		p12_path: Optional[str] = None,
		p12_password: Optional[str] = None,
		client_cert: Optional[str] = None,
		client_key: Optional[str] = None,
	):
		self.gateway_url = gateway_url.rstrip("/") if gateway_url else ""
		self.token = token
		self.cookie = cookie
		self.user = user
		self.password = password
		self.token_endpoint = token_endpoint or (
			f"{self.gateway_url}/knoxtoken/api/v1/token" if self.gateway_url else None
		)
		self.passcode_token = passcode_token
		self.verify = verify
		self.p12_path = p12_path
		self.p12_password = p12_password
		self.client_cert = client_cert
		self.client_key = client_key
		self._tmp_files: list[str] = []

	def _resolve_client_cert(self) -> Optional[Tuple[str, str]]:
		"""Return (cert_path, key_path) for requests session.cert, or None."""
		if self.p12_path:
			return self._extract_p12()
		if self.client_cert and self.client_key:
			return (self.client_cert, self.client_key)
		return None

	def _extract_p12(self) -> Tuple[str, str]:
		"""Extract cert and key from a PKCS#12 file into temp PEM files."""
		try:
			from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
		except ImportError:
			raise RuntimeError("cryptography package is required for P12 auth: pip install cryptography")

		password_bytes = self.p12_password.encode() if self.p12_password else None
		with open(self.p12_path, "rb") as f:
			p12_data = f.read()

		private_key, certificate, _ = pkcs12.load_key_and_certificates(p12_data, password_bytes)

		cert_pem = certificate.public_bytes(Encoding.PEM)
		key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

		cert_file = tempfile.NamedTemporaryFile(suffix=".crt", delete=False)
		cert_file.write(cert_pem)
		cert_file.flush()
		cert_file.close()

		key_file = tempfile.NamedTemporaryFile(suffix=".key", delete=False)
		key_file.write(key_pem)
		key_file.flush()
		key_file.close()

		self._tmp_files.extend([cert_file.name, key_file.name])
		atexit.register(self._cleanup_tmp_files)

		return (cert_file.name, key_file.name)

	def _cleanup_tmp_files(self) -> None:
		for path in self._tmp_files:
			try:
				os.unlink(path)
			except OSError:
				pass

	def build_session(self) -> requests.Session:
		session = requests.Session()
		session.verify = self.verify

		client_cert = self._resolve_client_cert()
		if client_cert:
			session.cert = client_cert

		# Priority: Explicit Cookie -> Knox token (as cookie for CDP) -> Passcode token -> Basic creds token exchange
		if self.cookie:
			session.headers["Cookie"] = self.cookie
			return session
		
		if self.token:
			# For CDP NiFi, Knox JWT tokens must be sent as cookies, not Bearer headers
			session.headers["Cookie"] = f"hadoop-jwt={self.token}"
			return session


		if self.passcode_token:
			# Prefer exchanging passcode for JWT via knoxtoken endpoint when available
			if self.token_endpoint:
				jwt = self._exchange_passcode_for_jwt()
				session.headers["Authorization"] = f"Bearer {jwt}"
				return session
			# Fallback: send passcode as header (may not work on all deployments)
			session.headers["X-Knox-Passcode"] = self.passcode_token
			return session

		if self.user and self.password and self.token_endpoint:
			jwt = self._fetch_knox_token()
			session.headers["Authorization"] = f"Bearer {jwt}"
			return session

		return session

	def _fetch_knox_token(self) -> str:
		# Default Knox token endpoint returns raw JWT or JSON with token fields
		resp = requests.get(
			self.token_endpoint,
			auth=(self.user, self.password),
			verify=self.verify,
			timeout=15,
		)
		resp.raise_for_status()
		try:
			data = resp.json()
			return data.get("access_token") or data.get("token") or data.get("accessToken")
		except ValueError:
			text = resp.text.strip()
			# Some envs return Base64-encoded token; detect and decode if needed
			try:
				decoded = base64.b64decode(text).decode("utf-8")
				if decoded.count(".") == 2:
					return decoded
			except Exception:
				pass
			return text

	def _exchange_passcode_for_jwt(self) -> str:
		"""Exchange Knox passcode token for JWT using Basic auth pattern passcode:<token>."""
		if not (self.passcode_token and self.token_endpoint):
			raise RuntimeError("Passcode token exchange requires token_endpoint and passcode token")
		import base64
		header = {
			"Authorization": "Basic " + base64.b64encode(f"passcode:{self.passcode_token}".encode()).decode(),
			"X-Requested-By": "nifi-mcp-server",
		}
		resp = requests.get(self.token_endpoint, headers=header, verify=self.verify, timeout=15)
		resp.raise_for_status()
		try:
			data = resp.json()
			return data.get("access_token") or data.get("token") or data.get("accessToken")
		except ValueError:
			return resp.text.strip()


