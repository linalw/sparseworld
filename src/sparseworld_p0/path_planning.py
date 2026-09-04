"""Deterministic candidate-route planning over observed camera trajectory."""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Any


@dataclass(frozen=True)
class TargetResolution:
    status: str
    target: dict[str, Any] | None = None
    candidates: tuple[dict[str, Any], ...] = ()


def resolve_target(objects: list[dict[str, Any]], query: str, object_id: str | None = None) -> TargetResolution:
    if object_id:
        for item in objects:
            if item.get("object_id") == object_id:
                return TargetResolution("resolved", item)
        return TargetResolution("target_not_found")
    needle = " ".join(str(query).lower().replace("_", " ").split())
    candidates = tuple(item for item in objects if needle and needle in _label(item))
    if not candidates:
        return TargetResolution("target_not_found")
    if len(candidates) > 1:
        return TargetResolution("ambiguous", candidates=candidates)
    return TargetResolution("resolved", candidates[0])


def plan_route(objects: list[dict[str, Any]], trajectory: list[dict[str, Any]], target_query: str, *, object_id: str | None = None, start_node_id: str | None = None) -> dict[str, Any]:
    resolution = resolve_target(objects, target_query, object_id)
    if resolution.status != "resolved":
        return {"status": resolution.status, "candidates": list(resolution.candidates), "route_status": "not_planned", "global_accuracy": "unvalidated"}
    if not trajectory:
        return {"status": "missing_trajectory", "target": resolution.target, "route_status": "not_planned", "global_accuracy": "unvalidated"}
    nodes = {str(item.get("keyframe_id")): item for item in trajectory if isinstance(item.get("position_xyz"), list) and len(item["position_xyz"]) == 3}
    if not nodes:
        return {"status": "missing_trajectory", "target": resolution.target, "route_status": "not_planned", "global_accuracy": "unvalidated"}
    ordered = [str(item["keyframe_id"]) for item in trajectory if str(item.get("keyframe_id")) in nodes]
    start = start_node_id if start_node_id in nodes else ordered[-1]
    target_xyz = resolution.target.get("geometry", {}).get("anchor_xyz")
    if not isinstance(target_xyz, list) or len(target_xyz) != 3:
        return {"status": "invalid_target_geometry", "target": resolution.target, "route_status": "not_planned", "global_accuracy": "unvalidated"}
    goal = min(nodes, key=lambda node_id: _distance(nodes[node_id]["position_xyz"], target_xyz))
    graph: dict[str, list[tuple[str, float]]] = {node_id: [] for node_id in nodes}
    for before, after in zip(ordered, ordered[1:]):
        length = _distance(nodes[before]["position_xyz"], nodes[after]["position_xyz"])
        graph[before].append((after, length)); graph[after].append((before, length))
    route, length = _dijkstra(graph, start, goal)
    if not route:
        return {"status": "disconnected", "target": resolution.target, "start_node_id": start, "goal_node_id": goal, "route_status": "not_planned", "global_accuracy": "unvalidated"}
    return {"status": "planned", "target": resolution.target, "start_node_id": start, "goal_node_id": goal, "nodes": route, "positions_xyz": [nodes[node_id]["position_xyz"] for node_id in route], "total_length_m": round(length, 6), "planning_basis": "observed_trajectory", "route_status": "planned_unverified", "global_accuracy": "unvalidated"}


def _label(item: dict[str, Any]) -> str:
    candidates = item.get("class_candidates", [])
    label = candidates[0].get("label", "") if candidates and isinstance(candidates[0], dict) else ""
    return " ".join(str(label).lower().replace("_", " ").split())


def _distance(first: list[float], second: list[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, second)))


def _dijkstra(graph: dict[str, list[tuple[str, float]]], start: str, goal: str) -> tuple[list[str], float]:
    queue = [(0.0, start, [start])]; best = {start: 0.0}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == goal:
            return path, cost
        if cost != best.get(node):
            continue
        for neighbour, edge_cost in sorted(graph[node]):
            candidate = cost + edge_cost
            if candidate < best.get(neighbour, float("inf")):
                best[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour, path + [neighbour]))
    return [], 0.0
