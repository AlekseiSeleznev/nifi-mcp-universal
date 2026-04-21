# Dashboard Architecture

This document defines the dashboard structure in `nifi-mcp-universal` for `v1.0.0`.

## Goals

- Keep runtime behavior backward-compatible.
- Reduce `web_ui.py` size and review complexity.
- Make dashboard changes safer with explicit contracts and tests.
- Avoid exposing secrets in rendered HTML.

## Module Split

- `gateway/gateway/web_ui.py`
  - request/auth checks
  - endpoint handlers (`/api/*`)
  - thin route wrappers delegating connect/edit/test operations
- `gateway/gateway/web_ui_helpers.py`
  - render glue (`render_dashboard`)
  - response helpers (`json_response`, `error_response`)
  - connection name validation regex
- `gateway/gateway/web_ui_services.py`
  - connect/edit/test orchestration logic (service layer)
- `gateway/gateway/web_ui_content.py`
  - translations dictionary (`_T`)
  - static dashboard template (`DASHBOARD_HTML`)
  - static docs pages (`DOCS_HTML`)
  - docs renderer (`render_docs`)
  - client-side Bearer prompt flow (no injected API key)

## API Error Contract

Dashboard mutation endpoints return JSON errors with this shape:

```json
{"error": "<message>"}
```

For `/api/test`, unsuccessful probe stays backward-compatible:

```json
{"ok": false, "error": "<message>"}
```

## Test Guardrails

Coverage is enforced by:

- `gateway/tests/test_web_ui.py` (lifecycle + error contract)
- `gateway/tests/test_ci_assets.py` (module split + docs presence checks)
- `gateway/tests/test_load_smoke.py` (high-frequency dashboard/API and session-switch smoke)

## Cross-Platform Notes

- Linux runtime smoke: `setup.sh` + `/health` + `/dashboard` + `/mcp`
- Windows CI smoke: deterministic static checks (`bash -n setup.sh`, compose file presence)
