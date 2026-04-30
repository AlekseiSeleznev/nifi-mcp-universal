# NiFi layout rules

## Names

- Use Russian names when the flow is for Russian-speaking operators.
- Prefix major stages with `10`, `20`, `30`, `90`.
- Prefix nested stages by extending the parent number: `30.10`, `30.20`, `30.20.10`.
- Never use `.00`.
- Keep the useful business name after the number.

## Comments

- Add comments to every object type that supports them: process groups, processors, input ports, output ports.
- Write comments in plain human Russian: why the object exists, what it receives/sends, where errors go.
- Avoid generic comments like “processes data”. The comment must help a future maintainer.
- Connections do not support comments. Keep connection names empty so the canvas does not become noisy.

## Layout

- Prefer one main vertical spine.
- Input port or start processor is at the top.
- Output port or finish processor is at the bottom.
- Side-effect/error/log processors go to the right column.
- Keep the right column close enough to the main spine for short readable
  branches, but leave a real routing corridor between the main processors and
  the side processors. Do not push errors far away just to avoid crossings.
- Use consistent vertical spacing by component type:
  - process group to process group: close enough that the connection label sits neatly between them;
  - processor to process group: a little more breathing room;
  - processor to processor: enough for the queue label without overlap.
  - input port to processor and processor to output port must be visually
    symmetrical when both ports have the same size; do not leave a long bottom
    tail if the top input link is compact.
- Do not leave large dead space unless it separates side branches from the main route.
- Side columns must be dynamic. A single log/error branch should stay close to
  the main line; dense fan-in can reserve a wider corridor for labels and lanes.

## Connections

- Use orthogonal routes: vertical and horizontal segments only.
- Main success path should usually have no bends when components are centered on the same x-axis.
- Error routes should leave to the right, travel on a side bus, then enter the log processor from the side.
- A single same-row branch should usually be a direct straight line. Do not add
  doglegs just to place the queue label if NiFi can place the label cleanly on
  the straight segment.
- Prefer the nearest useful side of the target. Do not force every connection
  into one common point: processors, groups and ports can be entered from top,
  bottom, left or right.
- Avoid giant “telephone wire” loops. A local side route is better than going
  far right/up/down and then coming back.
- Several routes into one output port must use separate lanes.
- Several routes into one processor, process group, or port must also use
  separate edge slots on the target side. Do not collapse fan-in into one
  center arrowhead: it looks like one thick wire and hides which branch goes where.
- Choose the target side globally: left, right, top, or bottom depending on the
  source position and blockers. Never hard-code “all error routes enter from the
  left” or “all branches enter from the top”.
- Fan-in/fan-out routes need two independent separations:
  1. separate bus lanes in the open corridor;
  2. separate entry/exit slots on the component edge.
  Solving only one of them still leaves overlapping lines near the target or source.
- For output ports, prefer a bottom lane when a direct vertical connection is
  blocked by another component. This makes the route read as “branch finished”.
- If the route would cross a queued label or another component, enter from the side instead of from the top.
- Set `labelIndex` so the connection label appears on a segment with enough free space.
- After routing, repack `labelIndex` values globally inside the process group.
  Local route scoring can miss two labels that are individually valid but overlap
  each other on the canvas.
- Empty every connection name.

## Verification

A flow is not finished until these checks are clean:

- no named connections;
- no missing comments on commentable objects;
- no `.00` numbering;
- no route segment intersects a component rectangle, except its own source/target;
- no connection label intersects a component or another label;
- no long collinear path overlap between different connections;
- screenshot is readable without guessing where a line goes.

## Apache NiFi UI geometry findings

Use these values from the current Apache NiFi frontend, not guessed screenshot sizes:

- Processor: `350 x 130`.
- Process group / remote process group: `384 x 176`.
- Input/output port: `240 x 48`; remote port: `240 x 80`.
- Funnel: `48 x 48`.
- Connection label width: `240`.
- Connection label row height: `19`; backpressure strip adds `3`.
- A connection label always has `Queued`; it also adds `From`/`To` rows for cross-process-group port connections and a `Name` row for selected relationships such as `success`, `failure`, `split`.
- `labelIndex` is centered on `bends[labelIndex]` when bends exist. Without bends the label is centered between calculated source/destination perimeter points.
- Do not use the old `apache/nifi-fds` repository for canvas geometry. It is a reusable Angular/Material design-system package; the live canvas sizes and connection behavior are in `apache/nifi` frontend files: `canvas.constants.ts` and `connection-renderer.ts`.

## Routing corrections learned from real visual review

- First prefer a straight vertical route for the main lane when source and destination share a centerline and there is no real blocker between them.
- Put error/log handlers far enough to the side so the 240px connection label fits between the main processor and side processor.
- For side routes, compute the lane from available corridor width; do not send every connection to the same point.
- Dense fan-in must be ranked before routing. Sort sources by their visible order,
  then assign target-edge slots in the same order. This avoids crossings and
  turns a fan-in into a readable comb instead of a bundle.
- Use actual component rectangles for label overlap checks, but inflated rectangles for path/segment clearance.
- Playwright screenshots remain mandatory after apply; REST geometry alone is not enough because the browser expands connection labels based on relationship rows.
- Use wide screenshots and, when the flow is larger than one viewport, capture
  multiple viewports or scroll/pan through the canvas. A route can look fine in
  a cropped screenshot and still create an ugly long loop outside the view.
