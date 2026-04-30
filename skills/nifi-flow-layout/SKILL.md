---
name: nifi-flow-layout
description: Beautify and standardize Apache NiFi flows. Use when a user asks to arrange NiFi processors/process groups, fix crossing connections, add human comments, apply hierarchical numbering like 10/20/30.10, or create a reusable visual layout for any NiFi flow.
---

# NiFi Flow Layout

Use this universal skill when any Apache NiFi flow must be readable a year later: clear names, useful comments, compact vertical flow, and connections that do not cross blocks. The skill has no environment-specific defaults: pass the NiFi URL, credentials/certificates, and target process group explicitly.

## Workflow

1. **Inspect first**
   - Read the target process group through NiFi REST.
   - Save a JSON snapshot before changing anything.
   - Run audit/dry-run before `apply`.

2. **Apply the house style**
   - Main route goes top-to-bottom.
   - Errors/logs/Teams go to a side column.
   - Connections are orthogonal: vertical/horizontal, no diagonals.
   - Connection names stay empty. Connections do not support comments in NiFi.
   - Every commentable object gets a useful human comment: processor, process group, input port, output port.
   - Names use hierarchical numbering: `10`, `20`, `30`, then `30.10`, `30.20`, then `30.20.10`. Never use `.00`.

3. **Verify visually**
   - Use Playwright when available to capture real DOM bounding boxes and a screenshot.
   - Treat route/label overlap with processors, process groups, ports, or queued boxes as a defect.

## Scripts

- `scripts/nifi_layout.py` — REST audit, dry-run, apply, geometry tests.
- `scripts/nifi_visual_check.cjs` — Playwright screenshot and DOM bounding-box capture.
- `references/layout-rules.md` — detailed rules and routing decisions.

## Typical commands

```bash
python3 scripts/nifi_layout.py \
  --base-url https://nifi.example.com/nifi-api \
  --group-id <process-group-id> \
  --cert /path/client.crt --key /path/client.key \
  --mode audit --recursive
```

```bash
python3 scripts/nifi_layout.py \
  --base-url https://nifi.example.com/nifi-api \
  --group-id <process-group-id> \
  --cert /path/client.crt --key /path/client.key \
  --mode dry-run --recursive --backup-dir ./nifi-backups
```

```bash
python3 scripts/nifi_layout.py \
  --base-url https://nifi.example.com/nifi-api \
  --group-id <process-group-id> \
  --cert /path/client.crt --key /path/client.key \
  --mode apply --recursive --backup-dir ./nifi-backups
```

## Safety rules

- Do not print secrets or certificate passphrases.
- Do not edit processor business properties unless the user explicitly asked.
- Default to `audit`/`dry-run`; use `apply` only when implementation is requested.
- Preserve revisions and current processor state; only update names, comments, positions, connection bends, labelIndex, and empty connection names.
- Before `apply`, always write a backup flow JSON using `--backup-dir`.
