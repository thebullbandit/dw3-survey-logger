"""drift_guardrail.py

Drift Guardrail (Leg Guidance)
==============================

Pure math + light formatting helpers for keeping a survey "leg" straight.
No UI code, no file IO.

Concepts:
- Leg start: P0
- Leg direction: unit vector u
- Step: ideal point spacing (default 50 ly)

For a candidate system position S:
- along_t: dot(S-P0, u)           (distance along the leg axis)
- drift_dist: |S - (P0 + u*along)| (cross-track / sideways drift)
- ideal_point_dist: distance to nearest step point along the leg
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   drift_guardrail.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


Vec3 = Tuple[float, float, float]


# ============================================================================
# FUNCTIONS
# ============================================================================

def _to_vec3(v: Sequence[float]) -> Optional[Vec3]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return None
    try:
        return (float(v[0]), float(v[1]), float(v[2]))
    except (TypeError, ValueError):
        return None


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def norm(a: Vec3) -> float:
    return (dot(a, a)) ** 0.5


def unit(vec: Vec3) -> Vec3:
    mag = norm(vec)
    if mag <= 0.0:
        return (0.0, 0.0, 0.0)
    return (vec[0] / mag, vec[1] / mag, vec[2] / mag)


def mean_unit(vectors: List[Vec3]) -> Vec3:
    if not vectors:
        return (0.0, 0.0, 0.0)
    sx = sum(v[0] for v in vectors)
    sy = sum(v[1] for v in vectors)
    sz = sum(v[2] for v in vectors)
    return unit((sx, sy, sz))


@dataclass(frozen=True)
# ============================================================================
# CLASSES
# ============================================================================

class DriftMetrics:
    system_name: str
    along_t: float
    drift_dist: float
    ideal_point_dist: float
    step_index: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "system": self.system_name,
            "drift_ly": self.drift_dist,
            "ideal_offset_ly": self.ideal_point_dist,
            "along_ly": self.along_t,
            "k": self.step_index,
        }


def drift_metrics(P0: Vec3, u: Vec3, step_ly: float, S: Vec3, system_name: str = "") -> DriftMetrics:
    """Compute drift + nearest ideal point distance for a candidate."""
    v = sub(S, P0)
    t = dot(v, u)  # along-track

    k = int(round(t / step_ly)) if step_ly else 0
    Pk = add(P0, mul(u, k * step_ly))
    proj = add(P0, mul(u, t))

    return DriftMetrics(
        system_name=system_name,
        along_t=float(t),
        drift_dist=float(norm(sub(S, proj))),
        ideal_point_dist=float(norm(sub(S, Pk))),
        step_index=k,
    )


def format_candidate_line(m: DriftMetrics) -> str:
    """Compact single-line UI string."""
    return (
        f"{m.system_name}: drift {m.drift_dist:5.1f} ly | "
        f"ideal {m.ideal_point_dist:5.1f} ly | along {m.along_t:+6.0f} ly"
    )


def build_direction_from_route(current_pos: Vec3, route_positions: List[Vec3], smooth_n: int = 3) -> Vec3:
    """Direction vector from NavRoute points (smoothed)."""
    vectors: List[Vec3] = []
    for p in route_positions[: max(1, smooth_n)]:
        vectors.append(sub(p, current_pos))
    return mean_unit(vectors)


def parse_navroute_positions(navroute_json: Dict[str, object]) -> List[Tuple[str, Vec3]]:
    """Extract (system_name, StarPos vec3) from NavRoute.json dict."""
    out: List[Tuple[str, Vec3]] = []
    route = navroute_json.get("Route")
    if not isinstance(route, list):
        return out

    for entry in route:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("StarSystem") or "")
        pos = _to_vec3(entry.get("StarPos") or [])
        if name and pos:
            out.append((name, pos))
    return out
