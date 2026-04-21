"""Service-layer operations for NiFi dashboard API routes."""

from __future__ import annotations

import os

from gateway.web_ui_helpers import (
    MAX_JSON_BODY_BYTES,
    MAX_MULTIPART_BODY_BYTES,
    enforce_content_length,
    error_response,
    json_response,
)


def _sanitized_connection_error(message: str = "connection failed"):
    return error_response(message, 502, ok=False)


async def connect_from_request(
    request,
    *,
    registry,
    client_manager,
    certs_dir: str,
    conn_name_re,
    connection_info_cls,
):
    """Connect to NiFi — accepts multipart (with cert upload) or JSON."""
    content_type = request.headers.get("content-type", "")
    max_body_bytes = MAX_MULTIPART_BODY_BYTES if "multipart" in content_type else MAX_JSON_BODY_BYTES
    too_large = enforce_content_length(request, max_body_bytes)
    if too_large:
        return too_large

    if "multipart" in content_type:
        form = await request.form()
        name = form.get("name", "").strip()
        url = form.get("url", "").strip()
        auth_method = form.get("auth_method", "none")
        verify_ssl = form.get("verify_ssl", "true").lower() == "true"
        readonly = form.get("readonly", "true").lower() == "true"

        cert_path = ""
        cert_key_path = ""

        # Validate name before using it in path construction
        if name and not conn_name_re.match(name):
            return error_response("Invalid connection name. Use only letters, digits, hyphens, underscores (max 63 chars).", 400)

        # Handle cert file upload (sanitize filename to prevent path traversal)
        # Max cert size: 1 MB (certs should be tiny; prevents DoS)
        max_cert_bytes = 1 * 1024 * 1024
        cert_file = form.get("cert_file")
        if cert_file and hasattr(cert_file, "read"):
            safe_filename = os.path.basename(cert_file.filename or "cert") or "cert"
            cert_dir = os.path.join(certs_dir, name)
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_filename)
            data = await cert_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Certificate file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_path = f"{name}/{safe_filename}"

        key_file = form.get("key_file")
        if key_file and hasattr(key_file, "read"):
            safe_key_filename = os.path.basename(key_file.filename or "key") or "key"
            cert_dir = os.path.join(certs_dir, name)
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_key_filename)
            data = await key_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Key file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_key_path = f"{name}/{safe_key_filename}"

        conn = connection_info_cls(
            name=name, url=url, auth_method=auth_method,
            cert_path=cert_path, cert_password=form.get("cert_password", ""),
            cert_key_path=cert_key_path,
            knox_token=form.get("knox_token", ""),
            knox_cookie=form.get("knox_cookie", ""),
            knox_passcode=form.get("knox_passcode", ""),
            knox_user=form.get("knox_user", ""),
            knox_password=form.get("knox_password", ""),
            knox_gateway_url=form.get("knox_gateway_url", ""),
            verify_ssl=verify_ssl, readonly=readonly,
        )
    else:
        body = await request.json()
        name = body.get("name", "").strip()
        url = body.get("url", "").strip()
        conn = connection_info_cls(
            name=name, url=url,
            auth_method=body.get("auth_method", "none"),
            verify_ssl=body.get("verify_ssl", True),
            readonly=body.get("readonly", True),
            knox_token=body.get("knox_token", ""),
            knox_cookie=body.get("knox_cookie", ""),
            knox_passcode=body.get("knox_passcode", ""),
            knox_user=body.get("knox_user", ""),
            knox_password=body.get("knox_password", ""),
            knox_gateway_url=body.get("knox_gateway_url", ""),
        )

    if not name or not url:
        return error_response("name and url are required", 400)

    if not conn_name_re.match(name):
        return error_response("Invalid connection name. Use only letters, digits, hyphens, underscores (max 63 chars).", 400)

    registry.add(conn)
    try:
        client_manager.connect(conn)
    except Exception:
        registry.remove(name)
        return _sanitized_connection_error()
    return json_response({"ok": True, "name": name, "nifi_version": conn.nifi_version})


async def edit_from_request(
    request,
    *,
    registry,
    client_manager,
    certs_dir: str,
    conn_name_re,
    connection_info_cls,
    build_client=None,
):
    """Edit connection — accepts multipart (with cert upload) or JSON."""
    content_type = request.headers.get("content-type", "")
    max_body_bytes = MAX_MULTIPART_BODY_BYTES if "multipart" in content_type else MAX_JSON_BODY_BYTES
    too_large = enforce_content_length(request, max_body_bytes)
    if too_large:
        return too_large

    if "multipart" in content_type:
        form = await request.form()
        old_name = form.get("old_name", "").strip()
        new_name = form.get("name", "").strip()
        url = form.get("url", "").strip()
        auth_method = form.get("auth_method")
        verify_ssl_str = form.get("verify_ssl")
        readonly_str = form.get("readonly")
    else:
        form = await request.json()
        old_name = form.get("old_name", "").strip()
        new_name = form.get("name", "").strip()
        url = form.get("url", "").strip()
        auth_method = form.get("auth_method")
        verify_ssl_str = form.get("verify_ssl")
        readonly_str = form.get("readonly")

    if not old_name or not new_name or not url:
        return error_response("old_name, name, and url are required", 400)

    if not conn_name_re.match(new_name):
        return error_response("Invalid connection name. Use only letters, digits, hyphens, underscores (max 63 chars).", 400)

    was_default = registry.active == old_name
    saved_default = registry.active

    old_conn = registry.get(old_name)
    old_conn_data = old_conn.to_dict() if old_conn else None

    # Resolve new values, falling back to old connection data
    resolved_auth = auth_method if auth_method is not None else (old_conn.auth_method if old_conn else "none")
    if isinstance(verify_ssl_str, str):
        resolved_verify = verify_ssl_str.lower() == "true"
    elif isinstance(verify_ssl_str, bool):
        resolved_verify = verify_ssl_str
    else:
        resolved_verify = old_conn.verify_ssl if old_conn else True
    if isinstance(readonly_str, str):
        resolved_readonly = readonly_str.lower() == "true"
    elif isinstance(readonly_str, bool):
        resolved_readonly = readonly_str
    else:
        resolved_readonly = old_conn.readonly if old_conn else True

    # Handle cert file uploads (multipart only)
    cert_path = old_conn.cert_path if old_conn else ""
    cert_key_path = old_conn.cert_key_path if old_conn else ""
    cert_password = old_conn.cert_password if old_conn else ""

    max_cert_bytes = 1 * 1024 * 1024
    if "multipart" in content_type:
        cert_file = form.get("cert_file")
        if cert_file and hasattr(cert_file, "read"):
            safe_filename = os.path.basename(cert_file.filename or "cert") or "cert"
            cert_dir = os.path.join(certs_dir, new_name)
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_filename)
            data = await cert_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Certificate file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_path = f"{new_name}/{safe_filename}"

        key_file = form.get("key_file")
        if key_file and hasattr(key_file, "read"):
            safe_key_filename = os.path.basename(key_file.filename or "key") or "key"
            cert_dir = os.path.join(certs_dir, new_name)
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_key_filename)
            data = await key_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Key file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_key_path = f"{new_name}/{safe_key_filename}"

        pw = form.get("cert_password")
        if pw:
            cert_password = pw

    # For sensitive fields: use new value if provided, else keep old
    def _resolve(key, old_val):
        v = form.get(key) if isinstance(form, dict) else form.get(key, "")
        if v and v != "***":
            return v
        return old_val

    conn = connection_info_cls(
        name=new_name, url=url,
        auth_method=resolved_auth,
        cert_path=cert_path,
        cert_password=cert_password,
        cert_key_path=cert_key_path,
        knox_token=_resolve("knox_token", old_conn.knox_token if old_conn else ""),
        knox_cookie=_resolve("knox_cookie", old_conn.knox_cookie if old_conn else ""),
        knox_passcode=_resolve("knox_passcode", old_conn.knox_passcode if old_conn else ""),
        knox_user=_resolve("knox_user", old_conn.knox_user if old_conn else ""),
        knox_password=_resolve("knox_password", old_conn.knox_password if old_conn else ""),
        knox_gateway_url=_resolve("knox_gateway_url", old_conn.knox_gateway_url if old_conn else ""),
        verify_ssl=resolved_verify,
        readonly=resolved_readonly,
    )
    trial_client = None
    try:
        if build_client is None:
            from gateway.nifi_client_manager import _build_client as build_client

        trial_client = build_client(conn)
        info = trial_client.get_version_info()
        conn.nifi_version = info.get("about", {}).get("version", "unknown")
    except Exception:
        return _sanitized_connection_error()
    finally:
        try:
            getattr(getattr(trial_client, "session", None), "close", lambda: None)()
        except Exception:
            pass

    registry.remove(old_name)
    client_manager.disconnect(old_name)
    registry.add(conn)
    try:
        client_manager.connect(conn)
    except Exception:
        registry.remove(new_name)
        if old_conn_data:
            restored = connection_info_cls(**old_conn_data)
            registry.add(restored)
            try:
                client_manager.connect(restored)
            except Exception:
                pass
        return _sanitized_connection_error()

    if was_default:
        registry.active = new_name
    elif saved_default and saved_default != old_name:
        registry.active = saved_default
    registry.save()
    return json_response({"ok": True, "name": new_name})


async def test_from_request(request, *, build_client, connection_info_cls, certs_dir: str):
    content_type = request.headers.get("content-type", "")
    max_body_bytes = MAX_MULTIPART_BODY_BYTES if "multipart" in content_type else MAX_JSON_BODY_BYTES
    too_large = enforce_content_length(request, max_body_bytes)
    if too_large:
        return too_large

    cert_path = ""
    cert_key_path = ""
    cert_password = ""
    max_cert_bytes = 1 * 1024 * 1024

    if "multipart" in content_type:
        body = await request.form()
        url = body.get("url", "").strip()
        auth_method = body.get("auth_method", "none")
        verify_ssl = body.get("verify_ssl", "true").lower() == "true"

        cert_file = body.get("cert_file")
        if cert_file and hasattr(cert_file, "read"):
            safe_filename = os.path.basename(cert_file.filename or "cert") or "cert"
            cert_dir = os.path.join(certs_dir, "__test__")
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_filename)
            data = await cert_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Certificate file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_path = f"__test__/{safe_filename}"

        key_file = body.get("key_file")
        if key_file and hasattr(key_file, "read"):
            safe_key_filename = os.path.basename(key_file.filename or "key") or "key"
            cert_dir = os.path.join(certs_dir, "__test__")
            os.makedirs(cert_dir, exist_ok=True)
            dest = os.path.join(cert_dir, safe_key_filename)
            data = await key_file.read()
            if len(data) > max_cert_bytes:
                return error_response("Key file too large (max 1 MB)", 400)
            with open(dest, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o600)
            cert_key_path = f"__test__/{safe_key_filename}"

        cert_password = body.get("cert_password", "")
    else:
        body = await request.json()
        url = body.get("url", "").strip()
        auth_method = body.get("auth_method", "none")
        verify_ssl = body.get("verify_ssl", True)

    if not url:
        return error_response("url is required", 400)

    conn = connection_info_cls(
        name="__test__", url=url,
        auth_method=auth_method,
        verify_ssl=verify_ssl,
        cert_path=cert_path,
        cert_key_path=cert_key_path,
        cert_password=cert_password,
        knox_token=body.get("knox_token", ""),
        knox_cookie=body.get("knox_cookie", ""),
        knox_passcode=body.get("knox_passcode", ""),
        knox_user=body.get("knox_user", ""),
        knox_password=body.get("knox_password", ""),
        knox_gateway_url=body.get("knox_gateway_url", ""),
    )
    client = None
    try:
        client = build_client(conn)
        info = client.get_version_info()
        version = info.get("about", {}).get("version", "unknown")
        return json_response({"ok": True, "nifi_version": version})
    except Exception:
        return error_response("connection test failed", status_code=502, ok=False)
    finally:
        try:
            client.session.close()
        except Exception:
            pass
