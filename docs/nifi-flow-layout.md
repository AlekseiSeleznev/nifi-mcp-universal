# Universal NiFi flow layout skill

`nifi-flow-layout` is a bundled Codex skill for making Apache NiFi process groups readable and maintainable. It is universal: it has no host-specific, customer-specific, or secret defaults. Always pass the NiFi REST API URL, credentials/certificates, and target process group explicitly.

Bundled source lives in:

```text
skills/nifi-flow-layout
```

Installed Codex location by default:

```text
~/.codex/skills/nifi-flow-layout
```

You can override the target directory with `CODEX_SKILLS_DIR`.

## Install

`setup.sh` and `install.ps1` install the bundled skill automatically. Manual install is also one command.

Linux/macOS/Git Bash:

```bash
./tools/install-codex-skills.sh
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test
```

Windows PowerShell:

```powershell
.\tools\install-codex-skills.ps1
python ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test
```

After installation, start a new Codex session or refresh the client skill registry; Codex will see the skill as `nifi-flow-layout`.

## Safety model

- Default workflow is `audit` first, then `dry-run`, then explicit `apply`.
- `dry-run` and `apply` save a backup flow JSON with `--backup-dir` before layout work.
- The script does not change business processor properties.
- The layout script only updates visual/maintenance metadata:
  - component positions;
  - processor/process group/input port/output port names when explicitly allowed by safe rename rules;
  - comments for commentable objects;
  - connection bends;
  - connection `labelIndex`;
  - empty connection names.
- Secrets, certificate passphrases, tokens, NiFi URLs, and group IDs are never stored in the skill. Pass them at runtime.

## Layout conventions

- Use Russian names and comments when the project is operated by Russian-speaking teams.
- Use hierarchical numbering:
  - root: `10`, `20`, `30`, `90`;
  - nested: `30.10`, `30.20`;
  - deeper: `30.20.10`;
  - never use `.00`.
- Keep connection names empty.
- Route the main flow top-to-bottom.
- Move error/log/Teams/side branches into side columns.
- Use orthogonal connection routes only: horizontal/vertical segments, no diagonals.
- Use fan-in/fan-out lanes and separate edge slots instead of stacking several lines into one unreadable bus.
- Keep a visible route clearance: 12px from labels/components and 32px between parallel lines in browser visual checks.
- Keep long return/fan-in corridors compact when possible: prefer about 64 canvas units between lanes, but reserve enough outside edge gap for the full 240px queued-label box so labels cannot touch processors or route lines.
- Treat line-to-line X/T crossings as hard defects; route around them rather than relying on visual intersections.
- Treat non-adjacent segments of the same connection as separate visual wires: self-overlapping U-turns and self-crossing loops are defects.
- Choose target entry side globally (`left`, `right`, `top`, `bottom`) based on source position and blockers; never force every branch to enter from the same side.
- Perform global label packing after route calculation, then a final route-vs-label nudge, so queued labels do not overlap blocks, other labels, or route lines.
- Use real NiFi UI dimensions:
  - Processor: `350x130`;
  - Process Group: `384x176`;
  - Input/Output Port: `240x48`;
  - Connection label width: `240`.
- Verify the final result visually with Playwright screenshot/DOM checks, not only REST geometry.

## Examples

Set reusable parameters in your shell without writing secrets into repository files.

```bash
export NIFI_API_BASE='https://nifi.example.com/nifi-api'
export NIFI_GROUP_ID='<process-group-id>'
```

### Audit

```bash
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py \
  --base-url "$NIFI_API_BASE" \
  --group-id "$NIFI_GROUP_ID" \
  --cert /path/to/client.crt \
  --key /path/to/client.key \
  --mode audit \
  --recursive \
  --report ./nifi-layout-audit.json
```

### Dry-run

```bash
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py \
  --base-url "$NIFI_API_BASE" \
  --group-id "$NIFI_GROUP_ID" \
  --cert /path/to/client.crt \
  --key /path/to/client.key \
  --mode dry-run \
  --recursive \
  --backup-dir ./nifi-layout-backups \
  --report ./nifi-layout-dry-run.json
```

### Apply

Run `apply` only after reviewing audit/dry-run output and confirming that the target NiFi instance is the intended one.

```bash
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py \
  --base-url "$NIFI_API_BASE" \
  --group-id "$NIFI_GROUP_ID" \
  --cert /path/to/client.crt \
  --key /path/to/client.key \
  --mode apply \
  --recursive \
  --backup-dir ./nifi-layout-backups \
  --report ./nifi-layout-apply.json
```

Bearer-token auth is also supported:

```bash
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py \
  --base-url "$NIFI_API_BASE" \
  --group-id "$NIFI_GROUP_ID" \
  --token "$NIFI_TOKEN" \
  --mode audit
```

### Screenshot visual check

Playwright is required for browser/DOM verification:

```bash
npm install -D playwright
npx playwright install chromium
```

Then run:

```bash
node ~/.codex/skills/nifi-flow-layout/scripts/nifi_visual_check.cjs \
  --url 'https://nifi.example.com/nifi/?processGroupId=<process-group-id>' \
  --cert /path/to/client.crt \
  --key /path/to/client.key \
  --out ./nifi-layout.png \
  --json ./nifi-layout-dom.json \
  --hide-controls
```

Treat any reported label/component/path overlap as a layout defect to fix before considering the flow complete.
