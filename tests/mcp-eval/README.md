# MCP-Eval suites

This project uses `lastmile-ai-mcp-eval` through the repository `Justfile`.

## Safe default suite

Run:

```bash
J=/home/as/Документы/AI_PROJECTS/casey-just/target/release/just
$J mcp-eval
```

The safe suite lives in `tests/mcp-eval/safe` and uses the local streamable HTTP
MCP endpoint:

```text
http://localhost:8085/mcp
```

It does not require LLM API keys and does not perform NiFi write operations. It
checks gateway health, MCP tool discovery, connection inventory reporting,
secret non-disclosure, unknown-connection failure behavior, and readonly write
blocking when a readonly registration is available.

## Integration suite

Run:

```bash
NIFI_MCP_EVAL_INTEGRATION=1 \
NIFI_MCP_EVAL_CONNECTION=<registered-connection-name> \
$J mcp-eval-integration
```

The integration suite is intentionally gated. Without
`NIFI_MCP_EVAL_INTEGRATION=1` the wrapper exits successfully with a skip
message. Integration checks only use read-only metadata/discovery tools.

## LLM-backed evals

The current baseline is deterministic and model-free. Agent-quality evals that
call `agent.generate_str(...)` require a configured LLM provider, for example:

```bash
export ANTHROPIC_API_KEY=...
# or
export OPENAI_API_KEY=...
```

Those tests should be added as a separate gated profile so routine local checks
remain safe and reproducible.
