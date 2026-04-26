set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

conformance := "/home/as/Документы/AI_PROJECTS/modelcontextprotocol-conformance/dist/index.js"
inspector := "/home/as/Документы/AI_PROJECTS/modelcontextprotocol-inspector/cli/build/index.js"
mcpeval_dir := "/home/as/Документы/AI_PROJECTS/lastmile-ai-mcp-eval"
pwsh := "/home/as/Документы/AI_PROJECTS/PowerShell-PowerShell/runtime-7.6.1-linux-x64/pwsh"
default_mcp_url := "http://localhost:8085/mcp"
default_health_url := "http://localhost:8085/health"

default:
    @echo "Available: test, health, mcp-init, mcp-tools-list, mcp-conformance, mcp-inspector-tools, mcp-eval, mcp-eval-integration, pwsh-version, pwsh-smoke, smoke"

test:
    cd gateway && { command -v python >/dev/null 2>&1 && python -m pytest tests -q || python3 -m pytest tests -q; }

health:
    curl -fsS "${HEALTH_URL:-{{default_health_url}}}"

mcp-init:
    node "{{conformance}}" server --url "${MCP_URL:-{{default_mcp_url}}}" --scenario server-initialize --output-dir "${MCP_CONFORMANCE_RESULTS:-/tmp/nifi-mcp-conformance}"

mcp-tools-list:
    node "{{conformance}}" server --url "${MCP_URL:-{{default_mcp_url}}}" --scenario tools-list --output-dir "${MCP_CONFORMANCE_RESULTS:-/tmp/nifi-mcp-conformance}"

mcp-conformance: mcp-init mcp-tools-list

mcp-inspector-tools:
    #!/usr/bin/env bash
    set -euo pipefail
    url="${MCP_URL:-{{default_mcp_url}}}"
    if [ -n "${NIFI_MCP_API_KEY:-}" ]; then
      node "{{inspector}}" --transport http --header "Authorization: Bearer ${NIFI_MCP_API_KEY}" --method tools/list "$url"
    else
      node "{{inspector}}" --transport http --method tools/list "$url"
    fi

mcp-eval path="tests/mcp-eval/safe":
    #!/usr/bin/env bash
    set -euo pipefail
    project_dir="$PWD"
    cd "{{mcpeval_dir}}"
    uv run mcp-eval run "$project_dir/{{path}}"

mcp-eval-integration path="tests/mcp-eval/integration":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "${NIFI_MCP_EVAL_INTEGRATION:-0}" != "1" ]; then
      echo "Skipping integration evals: set NIFI_MCP_EVAL_INTEGRATION=1 and NIFI_MCP_EVAL_CONNECTION=<registered-name>."
      exit 0
    fi
    : "${NIFI_MCP_EVAL_CONNECTION:?Set NIFI_MCP_EVAL_CONNECTION to a registered NiFi connection name}"
    project_dir="$PWD"
    cd "{{mcpeval_dir}}"
    uv run mcp-eval run "$project_dir/{{path}}"

pwsh-version:
    @"{{pwsh}}" -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'

pwsh-smoke:
    @"{{pwsh}}" -NoLogo -NoProfile -File tests/smoke/mcp-smoke.ps1

smoke: health mcp-conformance
