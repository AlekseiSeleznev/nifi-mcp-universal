#!/usr/bin/env python3
"""Audit and beautify Apache NiFi canvas layouts.

The script intentionally changes only visual/maintenance metadata:
positions, comments, connection bends, labelIndex, and empty connection names.
It does not edit processor business properties.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

# Match NiFi frontend CanvasConstants from apache/nifi.  These are not guessed:
# PROCESSOR=350x130, PORT=240x48, PROCESS_GROUP=384x176, FUNNEL=48x48.
# Connection labels are always 240px wide and their height depends on rows.
SIZE = {
    "PROCESSOR": (350.0, 130.0),
    "PROCESS_GROUP": (384.0, 176.0),
    "INPUT_PORT": (240.0, 48.0),
    "OUTPUT_PORT": (240.0, 48.0),
    "FUNNEL": (48.0, 48.0),
}
CONNECTION_LABEL_WIDTH = 240.0
CONNECTION_ROW_HEIGHT = 19.0
CONNECTION_BACKPRESSURE_HEIGHT = 3.0
# Fallback for old call sites; real connection labels use connection_label_size().
LABEL = (CONNECTION_LABEL_WIDTH, CONNECTION_ROW_HEIGHT * 2 + CONNECTION_BACKPRESSURE_HEIGHT)
PAD = 14.0
MAIN_X = {"PROCESSOR": 160.0, "PROCESS_GROUP": 144.0, "INPUT_PORT": 215.0, "OUTPUT_PORT": 215.0, "FUNNEL": 240.0}
MAIN_GAP = {
    ("PROCESS_GROUP", "PROCESS_GROUP"): 36.0,
    ("PROCESSOR", "PROCESS_GROUP"): 36.0,
    ("PROCESS_GROUP", "PROCESSOR"): 20.0,
    ("PROCESSOR", "PROCESSOR"): 20.0,
    # Port-to-processor/processor-to-port gaps should be symmetrical: the queue
    # label has enough air, but the link stays short and readable.
    ("INPUT_PORT", "PROCESSOR"): 8.0,
    ("PROCESSOR", "OUTPUT_PORT"): 8.0,
    ("PROCESS_GROUP", "OUTPUT_PORT"): 30.0,
    ("INPUT_PORT", "PROCESS_GROUP"): 36.0,
}
ERROR_COLUMN_GAP = 780.0
BUS_GAP = 300.0
LANE_GAP = 52.0

@dataclasses.dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float: return self.x
    @property
    def right(self) -> float: return self.x + self.w
    @property
    def top(self) -> float: return self.y
    @property
    def bottom(self) -> float: return self.y + self.h
    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2

    def inflate(self, p: float) -> "Rect":
        return Rect(self.x - p, self.y - p, self.w + 2*p, self.h + 2*p)

    def intersects(self, other: "Rect") -> bool:
        return not (self.right <= other.left or self.left >= other.right or self.bottom <= other.top or self.top >= other.bottom)

    def as_dict(self) -> Dict[str, float]:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "w": round(self.w, 3), "h": round(self.h, 3)}

@dataclasses.dataclass
class Node:
    id: str
    kind: str
    name: str
    x: float
    y: float
    comments: str = ""
    revision: int = 0
    raw: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def size(self) -> Tuple[float, float]:
        return SIZE.get(self.kind, SIZE["PROCESSOR"])

    def rect(self) -> Rect:
        w, h = self.size()
        return Rect(self.x, self.y, w, h)

    def with_pos(self, x: float, y: float) -> "Node":
        return dataclasses.replace(self, x=x, y=y)

@dataclasses.dataclass
class Conn:
    id: str
    source_id: str
    dest_id: str
    source_type: str
    dest_type: str
    source_group_id: Optional[str]
    dest_group_id: Optional[str]
    source_name: str
    dest_name: str
    relationships: Tuple[str, ...]
    name: str = ""
    bends: List[Dict[str, float]] = dataclasses.field(default_factory=list)
    label_index: int = 0
    revision: int = 0
    raw: Dict[str, Any] = dataclasses.field(default_factory=dict)

class NiFi:
    def __init__(self, base_url: str, cert: Optional[Tuple[str, str]], token: Optional[str], verify: bool):
        self.base_url = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.verify = verify
        if cert: self.s.cert = cert
        if token: self.s.headers.update({"Authorization": f"Bearer {token}"})
        if not verify:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    def req(self, method: str, path: str, **kw: Any) -> Any:
        last = None
        for i in range(8):
            try:
                r = self.s.request(method, self.base_url + "/" + path.lstrip("/"), timeout=60, **kw)
                if r.ok:
                    return r.json() if r.content else {}
                last = f"{method} {path} -> {r.status_code}\n{r.text[:2000]}"
            except Exception as e:  # pragma: no cover - diagnostic retry
                last = repr(e)
            time.sleep(0.2 + i * 0.2)
        raise RuntimeError(last)

    def flow(self, group_id: str) -> Dict[str, Any]:
        return self.req("GET", f"flow/process-groups/{group_id}")["processGroupFlow"]["flow"]

    def snapshot(self, group_id: str) -> Dict[str, Any]:
        return self.req("GET", f"flow/process-groups/{group_id}")

    def update_processor(self, node: Node, name: Optional[str], comments: Optional[str], x: Optional[float], y: Optional[float]) -> None:
        cur = self.req("GET", f"processors/{node.id}")
        was = cur["component"].get("state")
        if was == "RUNNING":
            self.req("PUT", f"processors/{node.id}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "STOPPED"})
            for _ in range(60):
                time.sleep(0.1)
                cur = self.req("GET", f"processors/{node.id}")
                if cur["component"].get("state") == "STOPPED": break
        comp: Dict[str, Any] = {"id": node.id}
        if name is not None: comp["name"] = name
        if x is not None and y is not None: comp["position"] = {"x": x, "y": y}
        if comments is not None:
            cfg = dict(cur["component"].get("config") or {})
            cfg["comments"] = comments
            comp["config"] = cfg
        self.req("PUT", f"processors/{node.id}", json={"revision": {"version": cur["revision"]["version"]}, "component": comp})
        if was == "RUNNING":
            cur = self.req("GET", f"processors/{node.id}")
            self.req("PUT", f"processors/{node.id}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "RUNNING"})

    def update_process_group(self, node: Node, name: Optional[str], comments: Optional[str], x: Optional[float], y: Optional[float]) -> None:
        cur = self.req("GET", f"process-groups/{node.id}")
        comp: Dict[str, Any] = {"id": node.id}
        if name is not None: comp["name"] = name
        if comments is not None: comp["comments"] = comments
        if x is not None and y is not None: comp["position"] = {"x": x, "y": y}
        self.req("PUT", f"process-groups/{node.id}", json={"revision": {"version": cur["revision"]["version"]}, "component": comp})

    def update_port(self, kind: str, node: Node, name: Optional[str], comments: Optional[str], x: Optional[float], y: Optional[float]) -> None:
        endpoint = "input-ports" if kind == "INPUT_PORT" else "output-ports"
        cur = self.req("GET", f"{endpoint}/{node.id}")
        was = cur["component"].get("state")
        if was == "RUNNING":
            self.req("PUT", f"{endpoint}/{node.id}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "STOPPED"})
            for _ in range(60):
                time.sleep(0.1)
                cur = self.req("GET", f"{endpoint}/{node.id}")
                if cur["component"].get("state") == "STOPPED": break
        comp: Dict[str, Any] = {"id": node.id}
        if name is not None: comp["name"] = name
        if comments is not None: comp["comments"] = comments
        if x is not None and y is not None: comp["position"] = {"x": x, "y": y}
        self.req("PUT", f"{endpoint}/{node.id}", json={"revision": {"version": cur["revision"]["version"]}, "component": comp})
        if was == "RUNNING":
            cur = self.req("GET", f"{endpoint}/{node.id}")
            self.req("PUT", f"{endpoint}/{node.id}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "RUNNING"})


    def _component_endpoint(self, typ: str, cid: str) -> Optional[str]:
        if typ == "PROCESSOR": return f"processors/{cid}"
        if typ == "INPUT_PORT": return f"input-ports/{cid}"
        if typ == "OUTPUT_PORT": return f"output-ports/{cid}"
        return None

    def _stop_component_if_running(self, typ: str, cid: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        endpoint = self._component_endpoint(typ, cid)
        if not endpoint:
            return None, None
        cur = self.req("GET", endpoint)
        state = cur["component"].get("state")
        if state == "RUNNING":
            self.req("PUT", f"{endpoint}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "STOPPED"})
            for _ in range(80):
                time.sleep(0.1)
                cur = self.req("GET", endpoint)
                if cur["component"].get("state") == "STOPPED":
                    break
            return endpoint, cur
        return None, None

    def _restart_component(self, endpoint: Optional[str]) -> None:
        if not endpoint:
            return
        cur = self.req("GET", endpoint)
        self.req("PUT", f"{endpoint}/run-status", json={"revision": {"version": cur["revision"]["version"]}, "state": "RUNNING"})

    def update_connection(self, conn: Conn, bends: List[Dict[str, float]], label_index: int, clear_name: bool = True) -> None:
        stopped: List[Optional[str]] = []
        src_ep, _ = self._stop_component_if_running(conn.source_type, conn.source_id)
        dst_ep, _ = self._stop_component_if_running(conn.dest_type, conn.dest_id)
        stopped.extend([src_ep, dst_ep])
        try:
            cur = self.req("GET", f"connections/{conn.id}")
            # NiFi expects the existing source/destination/relationships to remain present.
            # Source/destination are stopped because NiFi can otherwise reject the payload as
            # a relationship or destination change even when only geometry is changed.
            comp: Dict[str, Any] = dict(cur["component"])
            comp["id"] = conn.id
            comp["bends"] = bends
            comp["labelIndex"] = label_index
            if clear_name:
                comp["name"] = ""
            self.req("PUT", f"connections/{conn.id}", json={"revision": {"version": cur["revision"]["version"]}, "component": comp})
        finally:
            # Restart destination first, then source. If one side was already stopped it is ignored.
            for ep in reversed([x for x in stopped if x]):
                self._restart_component(ep)

def node_from(entity: Dict[str, Any], kind: str) -> Node:
    c = entity["component"]
    comments = c.get("comments") or (c.get("config") or {}).get("comments") or ""
    return Node(c["id"], kind, c.get("name") or "", c["position"]["x"], c["position"]["y"], comments, entity.get("revision", {}).get("version", 0), entity)

def conn_from(entity: Dict[str, Any]) -> Conn:
    c = entity["component"]
    rel = tuple(c.get("selectedRelationships") or c.get("relationships") or [])
    return Conn(c["id"], c["source"]["id"], c["destination"]["id"], c["source"]["type"], c["destination"]["type"], c.get("sourceGroupId") or c["source"].get("groupId"), c.get("destinationGroupId") or c["destination"].get("groupId"), c["source"].get("name", ""), c["destination"].get("name", ""), rel, c.get("name") or "", list(c.get("bends") or []), int(c.get("labelIndex") or 0), entity.get("revision", {}).get("version", 0), entity)

def parse_group(flow: Dict[str, Any]) -> Tuple[Dict[str, Node], List[Conn]]:
    nodes: Dict[str, Node] = {}
    for key, kind in [("processors", "PROCESSOR"), ("processGroups", "PROCESS_GROUP"), ("inputPorts", "INPUT_PORT"), ("outputPorts", "OUTPUT_PORT"), ("funnels", "FUNNEL")]:
        for e in flow.get(key, []) or []:
            n = node_from(e, kind)
            nodes[n.id] = n
    conns = [conn_from(e) for e in flow.get("connections", []) or []]
    return nodes, conns

def visual_id(conn: Conn, endpoint: str, current_group: str, nodes: Dict[str, Node]) -> str:
    if endpoint == "source":
        eid, gid = conn.source_id, conn.source_group_id
    else:
        eid, gid = conn.dest_id, conn.dest_group_id
    if eid in nodes:
        return eid
    if gid and gid != current_group and gid in nodes:
        return gid
    return eid

def is_errorish(node: Node) -> bool:
    text = f"{node.name} {node.comments}".lower()
    return any(s in text for s in ["ошиб", "error", "failure", "dead-letter", "лог ошибки", "логирует ошиб"])

def strip_number(name: str) -> str:
    return re.sub(r"^\s*\d+(?:\.\d+)*\s+", "", name).strip()

def comment_for(node: Node) -> str:
    if node.comments.strip():
        return node.comments.strip()
    n = strip_number(node.name) or node.kind
    if node.kind == "INPUT_PORT":
        return f"Вход в этот блок. Получает FlowFile от предыдущего шага и передает его дальше без скрытой бизнес-логики."
    if node.kind == "OUTPUT_PORT":
        return f"Выход из этого блока. Передает FlowFile следующему этапу после успешного завершения текущей логики."
    if node.kind == "PROCESS_GROUP":
        return f"Группа объединяет шаги «{n}», чтобы этот участок потока можно было читать и сопровождать отдельно."
    if is_errorish(node):
        return f"Фиксирует ошибочный сценарий для шага «{n}», чтобы сбой был виден в логах и не терялся в очередях."
    return f"Выполняет шаг «{n}» в общем сценарии. Комментарий нужен, чтобы было понятно, зачем объект стоит в потоке."

def classify_main(nodes: Dict[str, Node]) -> Tuple[List[Node], List[Node]]:
    if not nodes:
        return [], []
    xs = sorted(n.x for n in nodes.values())
    base_x = xs[min(len(xs)//2, len(xs)-1)]
    # Main lane is the visually left/central lane; far-right processors are side handlers.
    side: List[Node] = []
    main: List[Node] = []
    for n in nodes.values():
        if n.kind == "PROCESSOR" and n.x > base_x + 430:
            side.append(n)
        else:
            main.append(n)
    main.sort(key=lambda n: (n.y, n.x))
    side.sort(key=lambda n: (n.y, n.x))
    return main, side

def target_layout(nodes: Dict[str, Node], conns: Optional[List[Conn]] = None) -> Dict[str, Tuple[float, float]]:
    main, side = classify_main(nodes)
    result: Dict[str, Tuple[float, float]] = {}
    if not main:
        return result
    y = 0.0
    prev: Optional[Node] = None
    for i, n in enumerate(main):
        x = MAIN_X.get(n.kind, 160.0)
        if i == 0:
            y = 0.0
        elif prev is not None:
            ph = SIZE.get(prev.kind, SIZE["PROCESSOR"])[1]
            gap = MAIN_GAP.get((prev.kind, n.kind), 8.0)
            y = result[prev.id][1] + ph + LABEL[1] + gap
        result[n.id] = (x, y)
        prev = n
    if side:
        side_incoming: Dict[str, int] = collections.defaultdict(int)
        if conns:
            for c in conns:
                if c.dest_id in {s.id for s in side}:
                    side_incoming[c.dest_id] += 1
        max_fanin = max(side_incoming.values(), default=1)
        # A one-off log processor should stay near the main route. Dense fan-in needs
        # a wider corridor for labels and separate lanes, but not every side column does.
        dynamic_gap = min(ERROR_COLUMN_GAP, 670.0 + max(0, max_fanin - 1) * 30.0)
        side_x = MAIN_X["PROCESSOR"] + dynamic_gap
        # Put side handlers beside the nearest main step by original y. This keeps error routes horizontal.
        main_by_y = sorted(main, key=lambda n: n.y)
        used: Dict[float, int] = collections.defaultdict(int)
        for s in side:
            nearest = min(main_by_y, key=lambda m: abs(m.y - s.y)) if main_by_y else s
            sy = result.get(nearest.id, (nearest.x, nearest.y))[1]
            offset = used[sy] * 150.0
            used[sy] += 1
            result[s.id] = (side_x, sy + offset)
    return result

def with_targets(nodes: Dict[str, Node], targets: Dict[str, Tuple[float, float]]) -> Dict[str, Node]:
    return {i: (n.with_pos(*targets[i]) if i in targets else n) for i, n in nodes.items()}

def rects(nodes: Dict[str, Node], exclude: Iterable[str] = ()) -> List[Tuple[str, Rect]]:
    ex = set(exclude)
    return [(i, n.rect().inflate(PAD)) for i, n in nodes.items() if i not in ex]

def rects_actual(nodes: Dict[str, Node], exclude: Iterable[str] = ()) -> List[Tuple[str, Rect]]:
    ex = set(exclude)
    return [(i, n.rect()) for i, n in nodes.items() if i not in ex]

def segment_rect(a: Tuple[float, float], b: Tuple[float, float], thick: float = 2.0) -> Rect:
    x1, y1 = a; x2, y2 = b
    return Rect(min(x1, x2)-thick, min(y1, y2)-thick, abs(x1-x2)+2*thick, abs(y1-y2)+2*thick)

def orthogonal_segment(a: Tuple[float, float], b: Tuple[float, float]) -> Optional[Tuple[str, float, float, float]]:
    """Normalize an orthogonal segment for line-overlap diagnostics."""
    x1, y1 = a; x2, y2 = b
    if abs(x1 - x2) < 1.0 and abs(y1 - y2) >= 1.0:
        return ("v", round((x1 + x2) / 2.0, 1), min(y1, y2), max(y1, y2))
    if abs(y1 - y2) < 1.0 and abs(x1 - x2) >= 1.0:
        return ("h", round((y1 + y2) / 2.0, 1), min(x1, x2), max(x1, x2))
    return None

def segment_overlap_amount(a: Tuple[str, float, float, float], b: Tuple[str, float, float, float]) -> float:
    """Return overlap length for collinear segments; zero means no visual stacking."""
    if a[0] != b[0] or abs(a[1] - b[1]) > 2.0:
        return 0.0
    lo = max(a[2], b[2])
    hi = min(a[3], b[3])
    return max(0.0, hi - lo)

def route_points(src: Node, dst: Node, bends: List[Dict[str, float]]) -> List[Tuple[float, float]]:
    sr, dr = src.rect(), dst.rect()
    # Endpoint choice follows the dominant direction of the first/last segment.
    if bends:
        first = bends[0]; last = bends[-1]
        if first["x"] > sr.right: start = (sr.right, first["y"])
        elif first["x"] < sr.left: start = (sr.left, first["y"])
        else: start = (sr.cx, sr.bottom if first["y"] >= sr.cy else sr.top)
        if last["x"] > dr.right: end = (dr.right, last["y"])
        elif last["x"] < dr.left: end = (dr.left, last["y"])
        elif last["y"] < dr.top: end = (dr.cx, dr.top)
        else: end = (dr.cx, dr.bottom)
    else:
        if abs(sr.cx - dr.cx) < abs(sr.cy - dr.cy):
            start = (sr.cx, sr.bottom if dr.cy >= sr.cy else sr.top)
            end = (dr.cx, dr.top if dr.cy >= sr.cy else dr.bottom)
        else:
            start = (sr.right if dr.cx >= sr.cx else sr.left, sr.cy)
            end = (dr.left if dr.cx >= sr.cx else dr.right, dr.cy)
    return [start] + [(p["x"], p["y"]) for p in bends] + [end]

def terminal_is_group_port(typ: str, group_id: Optional[str], current_group: str) -> bool:
    """Mirror NiFi ConnectionRenderer.isGroup(): a port inside another PG is rendered as a group endpoint."""
    return typ in ("INPUT_PORT", "OUTPUT_PORT") and bool(group_id) and group_id != current_group

def connection_label_size(conn: Conn, current_group: str) -> Tuple[float, float]:
    """Return the real NiFi connection label size for route scoring.

    NiFi places the label at a bend point, not at the middle of the segment.
    Height is rows*19+3: optional From, optional To, optional relationship Name, mandatory Queued.
    """
    rows = 1  # Queued is always shown.
    if terminal_is_group_port(conn.source_type, conn.source_group_id, current_group):
        rows += 1
    if terminal_is_group_port(conn.dest_type, conn.dest_group_id, current_group):
        rows += 1
    if conn.relationships:
        rows += 1
    return CONNECTION_LABEL_WIDTH, rows * CONNECTION_ROW_HEIGHT + CONNECTION_BACKPRESSURE_HEIGHT

def label_rect(points: List[Tuple[float, float]], label_index: int, size: Tuple[float, float], bends: Optional[List[Dict[str, float]]] = None) -> Rect:
    if len(points) < 2:
        return Rect(0, 0, *size)
    # NiFi behavior: with bends, labelIndex points to a bend and the label is centered there.
    # Without bends, the label is centered between calculated start/end.
    if bends:
        idx = max(0, min(label_index, len(bends)-1))
        mx, my = bends[idx]["x"], bends[idx]["y"]
    else:
        a, b = points[0], points[-1]
        mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
    return Rect(mx - size[0]/2, my - size[1]/2, size[0], size[1])

def best_label_index(src: Node, dst: Node, bends: List[Dict[str, float]], nodes: Dict[str, Node], label_size: Tuple[float, float]) -> int:
    """Place the NiFi connection label on the safest visible bend point.

    A common mistake is to score segment midpoints. NiFi does not do that when bends exist: it centers the
    label directly on bends[labelIndex]. We therefore create enough bend candidates and score the actual label box.
    """
    pts = route_points(src, dst, bends)
    if not bends:
        return 0
    scored: List[Tuple[int, float, int]] = []
    for i, bend in enumerate(bends):
        lr = label_rect(pts, i, label_size, bends)
        collisions = 0
        for oid, r in rects_actual(nodes, exclude=[]):
            if lr.intersects(r):
                collisions += 100
        # Prefer labels on long open lanes and avoid first/last bends too close to component edges.
        nearest_component = min(
            (abs(bend["x"] - r.cx) + abs(bend["y"] - r.cy) for oid, r in rects(nodes, exclude=[])),
            default=9999.0,
        )
        edge_penalty = 25.0 if i in (0, len(bends) - 1) and len(bends) > 1 else 0.0
        scored.append((collisions, edge_penalty - min(nearest_component, 300.0) / 100.0, i))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return scored[0][2]

def best_label_index_avoiding(
    src: Node,
    dst: Node,
    bends: List[Dict[str, float]],
    nodes: Dict[str, Node],
    label_size: Tuple[float, float],
    occupied: List[Rect],
) -> int:
    """Pick a label bend that avoids both components and already placed labels."""
    if not bends:
        return 0
    pts = route_points(src, dst, bends)
    scored: List[Tuple[int, float, int]] = []
    for i, bend in enumerate(bends):
        lr = label_rect(pts, i, label_size, bends)
        collisions = 0
        for oid, r in rects_actual(nodes, exclude=[]):
            if lr.intersects(r):
                collisions += 100
        for other in occupied:
            if lr.intersects(other):
                collisions += 75
        # Prefer non-edge bends when scores are equal. Labels on first/last bends often sit
        # too close to the source/target even if they technically do not overlap.
        edge_penalty = 10.0 if i in (0, len(bends) - 1) and len(bends) > 1 else 0.0
        scored.append((collisions, edge_penalty, i))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return scored[0][2]

def route_cost(src: Node, dst: Node, bends: List[Dict[str, float]], label_index: int, nodes: Dict[str, Node], label_size: Tuple[float, float]) -> Tuple[int, float]:
    if label_index < 0:
        label_index = best_label_index(src, dst, bends, nodes, label_size)
    pts = route_points(src, dst, bends)
    collisions = 0
    for i in range(len(pts)-1):
        sr = segment_rect(pts[i], pts[i+1], 3.0)
        for oid, r in rects(nodes, exclude=[src.id, dst.id]):
            if sr.intersects(r):
                collisions += 100
    lr = label_rect(pts, label_index, label_size, bends)
    # Labels must not sit on any component, including their own source/destination.
    # NiFi renders labels as solid boxes, so touching endpoints still looks like overlap.
    for oid, r in rects(nodes, exclude=[]):
        if lr.intersects(r):
            collisions += 50
    length = sum(abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
    bends_penalty = len(bends) * 20.0
    return collisions, length + bends_penalty

def candidate_routes(src: Node, dst: Node, lane: int = 0) -> List[Tuple[List[Dict[str, float]], int]]:
    sr, dr = src.rect(), dst.rect()
    candidates: List[Tuple[List[Dict[str, float]], int]] = []
    # Direct route. Good for main vertical chain.
    candidates.append(([], -1))
    # Right-side route. Used only if it wins by geometry; no forced giant loops.
    bus_x = max(sr.right, dr.right) + BUS_GAP + lane * LANE_GAP
    y1, y2 = sr.cy, dr.cy
    candidates.append(([{"x": bus_x, "y": y1}, {"x": bus_x, "y": y2}, {"x": dr.left - 60, "y": y2}], -1))
    # Nearest-side local route. This is the normal choice for a branch to a
    # processor on the right: short horizontal, local vertical lane, short entry.
    if sr.cx < dr.cx:
        local_x = max(sr.right + 60.0 + lane * 40.0, dr.left - 90.0 - lane * 40.0)
        local_x = min(local_x, dr.left - 55.0)
    else:
        local_x = min(sr.left - 60.0 - lane * 40.0, dr.right + 90.0 + lane * 40.0)
        local_x = max(local_x, dr.right + 55.0)
    candidates.append(([{"x": local_x, "y": sr.cy}, {"x": local_x, "y": dr.cy}], -1))
    # Left-side route, useful for output ports and crowded targets.
    left_x = min(sr.left, dr.left) - 180 - lane * LANE_GAP
    low_y = max(sr.bottom, dr.bottom) + 70 + lane * 36
    candidates.append(([{"x": left_x, "y": sr.cy}, {"x": left_x, "y": low_y}, {"x": dr.left - 40, "y": low_y}, {"x": dr.left - 40, "y": dr.cy}], -1))
    # Simple doglegs.
    mid_y = (sr.cy + dr.cy) / 2
    candidates.append(([{"x": sr.cx, "y": mid_y}, {"x": dr.cx, "y": mid_y}], -1))
    mid_x = (sr.cx + dr.cx) / 2
    candidates.append(([{"x": mid_x, "y": sr.cy}, {"x": mid_x, "y": dr.cy}], -1))
    return candidates

def choose_route(src: Node, dst: Node, nodes: Dict[str, Node], label_size: Tuple[float, float], lane: int = 0) -> Tuple[List[Dict[str, float]], int]:
    scored = []
    for bends, li in candidate_routes(src, dst, lane):
        chosen_li = best_label_index(src, dst, bends, nodes, label_size) if li < 0 else li
        scored.append((route_cost(src, dst, bends, chosen_li, nodes, label_size), bends, chosen_li))
    scored.sort(key=lambda x: (x[0][0], x[0][1]))
    return scored[0][1], scored[0][2]

def old_bottom_output_route(src: Node, dst: Node, lane: int, total: int = 1) -> List[Dict[str, float]]:
    sr, dr = src.rect(), dst.rect()
    entry_x, entry_y = edge_slot(dr, "bottom", lane, total)
    source_x, _ = source_exit_point(src, "bottom", lane, total)
    lane_y = max(sr.bottom, dr.bottom) + 68.0 + lane * 46.0
    if sr.cx > dr.cx + 400.0:
        return [{"x": source_x, "y": lane_y}, {"x": entry_x, "y": lane_y}, {"x": entry_x, "y": entry_y}]
    if sr.cx > dr.cx + 120.0:
        lane_x = max(sr.right, dr.right) + 120.0 + lane * LANE_GAP
    else:
        lane_x = min(sr.left, dr.left) - 160.0 - lane * LANE_GAP
    return [{"x": lane_x, "y": sr.cy}, {"x": lane_x, "y": lane_y}, {"x": entry_x, "y": lane_y}, {"x": entry_x, "y": entry_y}]

def route_to_output(src: Node, dst: Node, nodes: Dict[str, Node], label_size: Tuple[float, float], lane: int, total: int = 1) -> Tuple[List[Dict[str, float]], int]:
    sr, dr = src.rect(), dst.rect()
    # Output ports are small, so a long bottom loop often looks worse than a
    # short side entry. Try both: shortest local side route and bottom-finish
    # route, then keep the one that does not cross intermediate processors.
    side = branch_target_side(src, dst)
    candidates: List[List[Dict[str, float]]] = []
    side_bends, _ = route_to_side(src, dst, label_size, lane, total, side)
    candidates.append(side_bends)
    candidates.append(old_bottom_output_route(src, dst, lane, total))
    # If the output is left/right of the source, also try direct side entry on that side.
    if abs(sr.cy - dr.cy) < 160.0:
        candidates.append([])
    scored: List[Tuple[Tuple[int, float], List[Dict[str, float]], int]] = []
    for bends in candidates:
        li = best_label_index(src, dst, bends, nodes, label_size) if bends else 0
        scored.append((route_cost(src, dst, bends, li, nodes, label_size), bends, li))
    scored.sort(key=lambda x: (x[0][0], x[0][1]))
    return scored[0][1], scored[0][2]

def branch_target_side(src: Node, dst: Node) -> str:
    """Choose the target side that makes the branch shortest and least surprising.

    This is deliberately global, not “always enter the left side”.  NiFi components can be
    entered from any side; the readable choice depends on where the source sits.
    """
    sr, dr = src.rect(), dst.rect()
    if sr.right <= dr.left:
        return "left"
    if dr.right <= sr.left:
        return "right"
    if sr.bottom <= dr.top:
        return "top"
    if dr.bottom <= sr.top:
        return "bottom"
    dx = dr.cx - sr.cx
    dy = dr.cy - sr.cy
    if abs(dx) >= abs(dy):
        return "left" if dx >= 0 else "right"
    return "top" if dy >= 0 else "bottom"

def edge_slot(rect: Rect, side: str, lane: int, total: int) -> Tuple[float, float]:
    """Return a distinct anchor point on the chosen target edge.

    Multiple incoming connections to the same object must not collapse into the same
    arrowhead.  Slots are ordered by source position, so top sources usually enter upper
    target slots and lines do not cross each other.
    """
    total = max(1, total)
    lane = max(0, min(lane, total - 1))
    if side in ("left", "right"):
        margin_top = 26.0
        margin_bottom = 18.0
        usable = max(1.0, rect.h - margin_top - margin_bottom)
        y = rect.top + margin_top + usable * (lane + 1) / (total + 1)
        x = rect.left - 48.0 if side == "left" else rect.right + 48.0
        return x, y
    margin_left = 30.0
    margin_right = 30.0
    usable = max(1.0, rect.w - margin_left - margin_right)
    x = rect.left + margin_left + usable * (lane + 1) / (total + 1)
    y = rect.top - 48.0 if side == "top" else rect.bottom + 48.0
    return x, y

def source_exit_point(src: Node, side: str, lane: int, total: int) -> Tuple[float, float]:
    """Spread exits too, so a processor with several branches does not create one thick line."""
    sr = src.rect()
    total = max(1, total)
    lane = max(0, min(lane, total - 1))
    if side == "left":
        # Target is to the left, so leave source through its left side.
        margin_top, margin_bottom = 26.0, 18.0
        y = sr.top + margin_top + max(1.0, sr.h - margin_top - margin_bottom) * (lane + 1) / (total + 1)
        return sr.left - 48.0, y
    if side == "right":
        margin_top, margin_bottom = 26.0, 18.0
        y = sr.top + margin_top + max(1.0, sr.h - margin_top - margin_bottom) * (lane + 1) / (total + 1)
        return sr.right + 48.0, y
    if side == "top":
        margin_left, margin_right = 30.0, 30.0
        x = sr.left + margin_left + max(1.0, sr.w - margin_left - margin_right) * (lane + 1) / (total + 1)
        return x, sr.top - 48.0
    margin_left, margin_right = 30.0, 30.0
    x = sr.left + margin_left + max(1.0, sr.w - margin_left - margin_right) * (lane + 1) / (total + 1)
    return x, sr.bottom + 48.0

def spread_coord(a: float, b: float, lane: int, total: int, min_gap: float = 60.0) -> float:
    """Pick a lane coordinate between two edges; fall back outside if the corridor is narrow."""
    lo, hi = min(a, b), max(a, b)
    if hi - lo >= min_gap * 2:
        return lo + (hi - lo) * (lane + 1) / (max(1, total) + 1)
    # No real corridor: create parallel outside lanes instead of stacking one line.
    mid = (a + b) / 2.0
    return mid + (lane - (max(1, total) - 1) / 2.0) * 44.0

def route_to_side(
    src: Node,
    dst: Node,
    label_size: Tuple[float, float],
    lane: int = 0,
    total: int = 1,
    target_side: Optional[str] = None,
) -> Tuple[List[Dict[str, float]], int]:
    sr, dr = src.rect(), dst.rect()
    side = target_side or branch_target_side(src, dst)
    if total <= 1 and side in ("left", "right"):
        # A single local branch does not need an artificial dogleg. Without bends,
        # NiFi centers the label on the straight segment; this is shorter and cleaner.
        if abs(sr.cy - dr.cy) < max(70.0, label_size[1] + 30.0):
            return [], 0
    entry_x, entry_y = edge_slot(dr, side, lane, total)
    # Source exits from the side facing the target entry.  This prevents the old “all branches
    # leave and enter through one center point” artifact.
    source_side = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[side]
    exit_x, exit_y = source_exit_point(src, source_side, lane, total)

    if side in ("left", "right"):
        # Horizontal branch: source -> unique vertical lane -> unique target slot.
        label_half = label_size[0] / 2.0
        if side == "left":
            # The label is centered on a bend. Keep every vertical lane far enough
            # from both components so the 240px label cannot sit on top of either one.
            safe_left = sr.right + label_half + 34.0
            safe_right = dr.left - label_half - 34.0
            lane_x = spread_coord(safe_left, safe_right, lane, total, min_gap=40.0)
            lane_x = min(lane_x, dr.left - 54.0)
            lane_x = max(lane_x, sr.right + 54.0) if sr.right < dr.left else lane_x
        else:
            safe_left = dr.right + label_half + 34.0
            safe_right = sr.left - label_half - 34.0
            lane_x = spread_coord(safe_left, safe_right, lane, total, min_gap=40.0)
            lane_x = max(lane_x, dr.right + 54.0)
            lane_x = min(lane_x, sr.left - 54.0) if dr.right < sr.left else lane_x
        bends = [
            {"x": exit_x, "y": exit_y},
            {"x": lane_x, "y": exit_y},
            {"x": lane_x, "y": entry_y},
            {"x": entry_x, "y": entry_y},
        ]
        return bends, -1

    # Vertical branch: source -> unique horizontal lane -> unique target slot.
    if side == "top":
        lane_y = spread_coord(sr.bottom + 58.0, dr.top - 58.0, lane, total, min_gap=100.0)
        lane_y = min(lane_y, dr.top - 54.0)
        lane_y = max(lane_y, sr.bottom + 54.0) if sr.bottom < dr.top else lane_y
    else:
        lane_y = spread_coord(dr.bottom + 58.0, sr.top - 58.0, lane, total, min_gap=100.0)
        lane_y = max(lane_y, dr.bottom + 54.0)
        lane_y = min(lane_y, sr.top - 54.0) if dr.bottom < sr.top else lane_y
    bends = [
        {"x": exit_x, "y": exit_y},
        {"x": exit_x, "y": lane_y},
        {"x": entry_x, "y": lane_y},
        {"x": entry_x, "y": entry_y},
    ]
    return bends, -1

def route_connections(group_id: str, nodes: Dict[str, Node], conns: List[Conn]) -> Dict[str, Tuple[List[Dict[str, float]], int]]:
    routed: Dict[str, Tuple[List[Dict[str, float]], int]] = {}
    # Pre-rank fan-in groups before routing.  This is the key to avoiding visual line
    # stacking: connections going into the same target side receive ordered edge slots
    # and ordered bus lanes instead of all sharing the target center.
    branch_groups: Dict[Tuple[str, str], List[str]] = collections.defaultdict(list)
    branch_rank: Dict[str, Tuple[int, int, str]] = {}
    output_groups: Dict[str, List[str]] = collections.defaultdict(list)
    output_rank: Dict[str, Tuple[int, int]] = {}
    for c in conns:
        sid = visual_id(c, "source", group_id, nodes)
        did = visual_id(c, "dest", group_id, nodes)
        if sid not in nodes or did not in nodes:
            continue
        src, dst = nodes[sid], nodes[did]
        aligned_main = abs(src.rect().cx - dst.rect().cx) < 70 and src.rect().bottom <= dst.rect().top
        if dst.kind == "OUTPUT_PORT":
            output_groups[dst.id].append(c.id)
        if dst.kind == "PROCESSOR" and not aligned_main:
            side = branch_target_side(src, dst)
            # Only rank true branches. Local processor-to-processor main path is left for choose_route().
            horizontal_gap = abs(dst.rect().cx - src.rect().cx) > 280
            vertical_gap = abs(dst.rect().cy - src.rect().cy) > 220
            if horizontal_gap or vertical_gap:
                branch_groups[(dst.id, side)].append(c.id)
    conn_by_id = {c.id: c for c in conns}
    for (dst_id, side), ids in branch_groups.items():
        if side in ("left", "right"):
            ids.sort(key=lambda cid: (nodes[visual_id(conn_by_id[cid], "source", group_id, nodes)].rect().cy, cid))
        else:
            ids.sort(key=lambda cid: (nodes[visual_id(conn_by_id[cid], "source", group_id, nodes)].rect().cx, cid))
        for i, cid in enumerate(ids):
            branch_rank[cid] = (i, len(ids), side)
    for dst_id, ids in output_groups.items():
        # For output ports, sort by source Y first so stacked branches keep their
        # visible order and receive different bottom slots.
        ids.sort(key=lambda cid: (nodes[visual_id(conn_by_id[cid], "source", group_id, nodes)].rect().cy, cid))
        for i, cid in enumerate(ids):
            output_rank[cid] = (i, len(ids))
    for c in conns:
        sid = visual_id(c, "source", group_id, nodes)
        did = visual_id(c, "dest", group_id, nodes)
        if sid not in nodes or did not in nodes:
            routed[c.id] = ([], 0)
            continue
        src, dst = nodes[sid], nodes[did]
        label_size = connection_label_size(c, group_id)
        if dst.kind == "OUTPUT_PORT":
            # The normal main-chain finish is a short vertical connection.
            # Side lanes are only for secondary branches into the same output port.
            aligned = abs(src.rect().cx - dst.rect().cx) < 70 and src.rect().bottom <= dst.rect().top
            blocked_below = any(
                n.id not in (src.id, dst.id)
                and abs(n.rect().cx - src.rect().cx) < 120
                and n.rect().top > src.rect().bottom
                and n.rect().bottom < dst.rect().top
                for n in nodes.values()
            )
            if aligned and not blocked_below:
                routed[c.id] = ([], 0)
            else:
                lane, total = output_rank.get(c.id, (0, 1))
                bends, li = route_to_output(src, dst, nodes, label_size, lane, total)
                if li < 0:
                    li = best_label_index(src, dst, bends, nodes, label_size)
                routed[c.id] = (bends, li)
            continue
        if c.id in branch_rank:
            lane, total, side = branch_rank[c.id]
            bends, li = route_to_side(src, dst, label_size, lane, total, side)
            if li < 0:
                li = best_label_index(src, dst, bends, nodes, label_size)
            routed[c.id] = (bends, li)
            continue
        # Main lane rule: if the next component is directly below on the same centerline,
        # keep the connection straight. This is the visual style the user expects in NiFi:
        # block → queue label → block, without side doglegs for normal success flow.
        aligned_main = abs(src.rect().cx - dst.rect().cx) < 70 and src.rect().bottom <= dst.rect().top
        blocker = any(
            n.id not in (src.id, dst.id)
            and abs(n.rect().cx - src.rect().cx) < 130
            and n.rect().top > src.rect().bottom
            and n.rect().bottom < dst.rect().top
            for n in nodes.values()
        )
        if aligned_main and not blocker:
            routed[c.id] = ([], 0)
            continue
        bends, li = choose_route(src, dst, nodes, label_size, 0)
        routed[c.id] = (bends, li)
    # Second pass: NiFi labels are solid boxes, and local route scoring cannot see labels
    # that will be placed by other connections. Pack labelIndex values so queue labels do
    # not overlap each other when several branches share the same visual area.
    occupied_labels: List[Rect] = []
    for c in sorted(conns, key=lambda cc: (nodes.get(visual_id(cc, "source", group_id, nodes), Node("", "PROCESSOR", "", 0, 0)).y, cc.id)):
        sid = visual_id(c, "source", group_id, nodes)
        did = visual_id(c, "dest", group_id, nodes)
        if sid not in nodes or did not in nodes:
            continue
        bends, li = routed.get(c.id, ([], 0))
        label_size = connection_label_size(c, group_id)
        if bends:
            li = best_label_index_avoiding(nodes[sid], nodes[did], bends, nodes, label_size, occupied_labels)
            routed[c.id] = (bends, li)
        pts = route_points(nodes[sid], nodes[did], bends)
        occupied_labels.append(label_rect(pts, li, label_size, bends))
    return routed

def audit_names_comments(nodes: Dict[str, Node], conns: List[Conn]) -> Dict[str, Any]:
    missing_comments = [(n.kind, n.id, n.name) for n in nodes.values() if n.kind != "FUNNEL" and not n.comments.strip()]
    named_connections = [(c.id, c.name) for c in conns if c.name]
    dot00 = [(n.kind, n.id, n.name) for n in nodes.values() if re.search(r"(^|\.)00(\D|$)", n.name)]
    return {"missing_comments": missing_comments, "named_connections": named_connections, "dot00_names": dot00}

def route_report(group_id: str, nodes: Dict[str, Node], conns: List[Conn], routes: Dict[str, Tuple[List[Dict[str, float]], int]]) -> List[Dict[str, Any]]:
    issues = []
    label_rects: List[Tuple[str, Rect]] = []
    all_segments: List[Tuple[str, int, Tuple[str, float, float, float]]] = []
    for c in conns:
        sid = visual_id(c, "source", group_id, nodes)
        did = visual_id(c, "dest", group_id, nodes)
        if sid not in nodes or did not in nodes:
            continue
        bends, li = routes.get(c.id, (c.bends, c.label_index))
        pts = route_points(nodes[sid], nodes[did], bends)
        for i in range(len(pts)-1):
            seg = segment_rect(pts[i], pts[i+1], 3.0)
            hits = [oid for oid, r in rects(nodes, exclude=[sid, did]) if seg.intersects(r)]
            if hits:
                issues.append({"connection": c.id, "type": "segment_intersects_component", "segment": i, "hits": hits})
            norm = orthogonal_segment(pts[i], pts[i+1])
            if norm and (norm[3] - norm[2]) > 12.0:
                all_segments.append((c.id, i, norm))
        lr = label_rect(pts, li, connection_label_size(c, group_id), bends)
        hits = [oid for oid, r in rects_actual(nodes, exclude=[]) if lr.intersects(r)]
        if hits:
            issues.append({"connection": c.id, "type": "label_intersects_component", "hits": hits, "label": lr.as_dict()})
        for oid, other in label_rects:
            if lr.intersects(other):
                issues.append({"connection": c.id, "type": "label_intersects_label", "other": oid})
        label_rects.append((c.id, lr))
    for i in range(len(all_segments)):
        ca, ia, sa = all_segments[i]
        for j in range(i + 1, len(all_segments)):
            cb, ib, sb = all_segments[j]
            if ca == cb:
                continue
            overlap = segment_overlap_amount(sa, sb)
            # Tiny shared endpoint touches are fine. Longer collinear overlap creates the
            # “one thick wire” problem the skill must prevent.
            if overlap > 20.0:
                issues.append({
                    "connection": ca,
                    "type": "segment_overlaps_segment",
                    "segment": ia,
                    "other_connection": cb,
                    "other_segment": ib,
                    "overlap": round(overlap, 1),
                    "orientation": sa[0],
                })
    return issues

def backup(api: NiFi, group_id: str, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / f"nifi-flow-{group_id}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(api.snapshot(group_id), ensure_ascii=False, indent=2), encoding="utf-8")
    return out

def iter_groups(api: NiFi, root_id: str, recursive: bool) -> Iterable[Tuple[str, Dict[str, Any]]]:
    flow = api.flow(root_id)
    yield root_id, flow
    if recursive:
        for pg in flow.get("processGroups", []) or []:
            yield from iter_groups(api, pg["component"]["id"], recursive=True)

def apply_group(api: NiFi, group_id: str, flow: Dict[str, Any], mode: str, rename: bool = False) -> Dict[str, Any]:
    nodes, conns = parse_group(flow)
    before = audit_names_comments(nodes, conns)
    targets = target_layout(nodes, conns)
    next_nodes = with_targets(nodes, targets)
    routes = route_connections(group_id, next_nodes, conns)
    issues = route_report(group_id, next_nodes, conns, routes)
    planned = {"group_id": group_id, "node_moves": [], "connection_routes": [], "before_audit": before, "route_issues": issues}

    for nid, n in nodes.items():
        x, y = targets.get(nid, (n.x, n.y))
        new_comment = comment_for(n)
        new_name = n.name
        if rename and n.kind in ("PROCESSOR", "PROCESS_GROUP") and re.search(r"(^|\.)00(\D|$)", n.name):
            new_name = re.sub(r"(^|\.)00(?=\D|$)", lambda m: "10" if m.group(1) == "" else m.group(1) + "10", n.name)
        changed = abs(n.x-x) > 0.1 or abs(n.y-y) > 0.1 or new_comment != n.comments or new_name != n.name
        if changed:
            planned["node_moves"].append({"id": nid, "kind": n.kind, "name": n.name, "to_name": new_name, "from": {"x": n.x, "y": n.y}, "to": {"x": x, "y": y}, "comment_changed": new_comment != n.comments})
            if mode == "apply":
                if n.kind == "PROCESSOR":
                    api.update_processor(n, new_name if new_name != n.name else None, new_comment if new_comment != n.comments else None, x, y)
                elif n.kind == "PROCESS_GROUP":
                    api.update_process_group(n, new_name if new_name != n.name else None, new_comment if new_comment != n.comments else None, x, y)
                elif n.kind in ("INPUT_PORT", "OUTPUT_PORT"):
                    api.update_port(n.kind, n, new_name if new_name != n.name else None, new_comment if new_comment != n.comments else None, x, y)

    for c in conns:
        bends, li = routes.get(c.id, ([], 0))
        need = c.name != "" or c.bends != bends or c.label_index != li
        if need:
            planned["connection_routes"].append({"id": c.id, "source": c.source_name, "dest": c.dest_name, "clear_name": bool(c.name), "bends": bends, "labelIndex": li})
            if mode == "apply":
                api.update_connection(c, bends, li, clear_name=True)
    return planned

def cmd_self_test() -> None:
    a = Rect(0, 0, 10, 10); b = Rect(9, 9, 5, 5); c = Rect(11, 11, 5, 5)
    assert a.intersects(b)
    assert not a.intersects(c)
    src = Node("a", "PROCESSOR", "A", 0, 0)
    dst = Node("b", "PROCESSOR", "B", 0, 220)
    nodes = {"a": src, "b": dst, "x": Node("x", "PROCESSOR", "X", 420, 0)}
    bends, li = choose_route(src, dst, nodes, LABEL)
    assert isinstance(bends, list) and isinstance(li, int)
    assert not re.search(r"(^|\.)00(\D|$)", "30.10 Test")
    assert re.search(r"(^|\.)00(\D|$)", "30.00 Test")
    print("self-test ok")

def main() -> None:
    p = argparse.ArgumentParser(description="Audit/dry-run/apply NiFi visual layout rules")
    p.add_argument("--base-url", help="NiFi API base URL, e.g. https://nifi.example.com/nifi-api")
    p.add_argument("--group-id", help="Root process group id")
    p.add_argument("--cert", help="Client certificate PEM")
    p.add_argument("--key", help="Client key PEM")
    p.add_argument("--token", help="Bearer token")
    p.add_argument("--verify", default="false", help="TLS verify: true/false or CA bundle path")
    p.add_argument("--mode", choices=["audit", "dry-run", "apply", "self-test"], default="audit")
    p.add_argument("--recursive", action="store_true", help="Process nested groups too")
    p.add_argument("--backup-dir", default="./nifi-layout-backups")
    p.add_argument("--rename", action="store_true", help="Allow safe numbering cleanup such as .00 -> .10")
    p.add_argument("--report", help="Write JSON report to this file")
    args = p.parse_args()
    if args.mode == "self-test":
        cmd_self_test(); return
    if not args.base_url or not args.group_id:
        p.error("--base-url and --group-id are required unless --mode self-test")
    verify: Any = False if str(args.verify).lower() in ("0", "false", "no") else (True if str(args.verify).lower() in ("1", "true", "yes") else args.verify)
    cert = (args.cert, args.key) if args.cert and args.key else None
    api = NiFi(args.base_url, cert, args.token, verify)
    backup_path = backup(api, args.group_id, Path(args.backup_dir)) if args.mode in ("dry-run", "apply") else None
    all_reports = []
    for gid, flow in iter_groups(api, args.group_id, args.recursive):
        all_reports.append(apply_group(api, gid, flow, args.mode, rename=args.rename))
    report = {"mode": args.mode, "root_group_id": args.group_id, "backup": str(backup_path) if backup_path else None, "groups": all_reports}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
