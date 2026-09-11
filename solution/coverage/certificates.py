"""Q3/Q4 continuous coverage certificates.

The returned certificates are geometric discovery guarantees only. They do
not claim that an online controller will finish within a real-time budget.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class OmniCertificate:
    radius_m: float
    station_radius_m: float
    max_distance_m: float
    margin_m: float
    certified: bool


def omni_skeleton(a_m=1135.0, safe_radius_m=1000.0):
    """Origin plus six vertices, with independent station identifiers."""
    points = {"origin": (0.0, 0.0)}
    for k in range(6):
        angle = k * math.pi / 3
        points[f"v{k}"] = (a_m * math.cos(angle), a_m * math.sin(angle))
    # On each 60 degree sector the farthest boundary point is at an endpoint
    # because r^2+a^2-2ra cos(30deg) is convex in r.
    endpoint = max(
        math.sqrt(r*r + a_m*a_m - 2*r*a_m*math.cos(math.pi/6))
        for r in (1000.0, 1800.0)
    )
    # The central disk is covered by origin; the endpoint check covers the
    # annulus between the central disk and target boundary.
    margin = safe_radius_m - endpoint
    return points, OmniCertificate(1800.0, a_m, endpoint, margin, margin >= 0)


def check_omni_parameters(values=(1130.0, 1135.0, 1140.0, 1150.0, 1200.0),
                          safe_radius_m=1000.0):
    out = []
    for a in values:
        points, cert = omni_skeleton(a, safe_radius_m)
        out.append({"a_m": a, "points": points, "max_distance_m": cert.max_distance_m,
                    "margin_m": cert.margin_m, "certified": cert.certified})
    return out


def triangular_grid(spacing_m=995.0, target_radius_m=1800.0, margin_m=1e-6):
    """All vertices of closed triangles intersecting the target disk.

    A triangle is retained when its bounding box intersects the disk; the
    conservative vertex set is then filtered to a finite expanded disk. The
    certificate is checked by triangle diameter and convex-combination proof,
    not by random sampling.
    """
    h = spacing_m * math.sqrt(3) / 2
    verts, triangles = set(), []
    # Generous finite index range covers every triangle whose closure meets D.
    n = int(math.ceil((target_radius_m + spacing_m) / h)) + 1
    for row in range(-n, n + 1):
        y = row * h
        offset = 0.5 * spacing_m if row & 1 else 0.0
        for col in range(-n, n + 1):
            x = col * spacing_m + offset
            a = (x, y); b = (x + spacing_m, y); c = (x + spacing_m/2, y + h)
            for tri in ((a, b, c), ((x, y), (x + spacing_m/2, y-h), (x + spacing_m, y))):
                xmin=min(p[0] for p in tri); xmax=max(p[0] for p in tri)
                ymin=min(p[1] for p in tri); ymax=max(p[1] for p in tri)
                # Bounding-box disk intersection is a necessary prefilter.
                # Distance from the origin to the rectangle: zero when the
                # rectangle contains the origin, otherwise nearest corner.
                dx=max(xmin, 0, -xmax)
                dy=max(ymin, 0, -ymax)
                # The farthest corner must not be used as an intersection
                # test: a triangle is retained when its rectangle reaches D.
                if dx*dx + dy*dy <= target_radius_m*target_radius_m + margin_m:
                    triangles.append(tri); verts.update(tri)
    vertices = sorted(verts)
    checks = [max(math.dist(p, q) for p in tri for q in tri) <= spacing_m + margin_m
              for tri in triangles]
    return {"spacing_m": spacing_m, "vertices": vertices, "triangles": triangles,
            "triangle_count": len(triangles), "vertex_count": len(vertices),
            "diameter_checks": all(checks), "target_radius_m": target_radius_m,
            "certificate": "every retained triangle has diameter <= spacing; each source is a convex combination of its vertices, so at least one vertex lies in every closed emitting half-plane"}


def verify_directional_certificate(grid):
    return bool(grid["triangles"] and grid["diameter_checks"] and grid["spacing_m"] < 1000)
