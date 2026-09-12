"""Public-history features for candidate-action policies.

No scenario object, source count, radius, type, heading, reward, or evaluator
field is accepted by these functions.
"""
import math
import numpy as np


def angle_features(deg):
    if deg is None:
        return (0.0, 0.0)
    a = math.radians(float(deg))
    return math.sin(a), math.cos(a)


def channel_token(state):
    obs = state.get("observations", [])
    last = obs[-1] if obs else {}
    s, c = angle_features(last.get("svd_deg"))
    return np.array([
        {"UNKNOWN": 0, "FOUND": 1, "LOCALIZING": 2, "CLEARABLE": 3,
         "CLEARED": 4, "ABSENT_CERTIFIED": 5}.get(state.get("status", "UNKNOWN"), -1),
        float(len(obs)), s, c, float(state.get("area_m2", 0.0)),
        float(state.get("diameter_m", 0.0)), float(state.get("mec_radius_m", 0.0)),
        float(state.get("safe_clear", False)), float(state.get("cover_progress", 0.0)),
    ], dtype=np.float32)


def public_state(global_state, channel_states, candidates):
    """Return a fixed-shape dict suitable for a Set/Transformer encoder."""
    return {
        "global": np.asarray([
            *global_state.get("position", (0.0, 0.0)),
            float(global_state.get("current_channel", 1)),
            float(global_state.get("virtual_time_s", 0.0)),
            float(global_state.get("remaining_real_duration_s", 0.0)),
            float(global_state.get("discovered_count", 0)),
            float(global_state.get("cleared_count", 0)),
            float(global_state.get("unresolved_count", 20)),
            float(global_state.get("problem", 3)),
            float(global_state.get("coverage_progress", 0.0)),
        ], dtype=np.float32),
        "channels": np.stack([channel_token(s) for s in channel_states], axis=0),
        "candidates": np.asarray([[
            {"COVER": 0, "LOCALIZE": 1, "MULTI_MEASURE": 2, "CLEAR": 3,
             "PROBE_CLEAR": 4, "ROUTE_CLEAR": 5, "EXIT": 6}.get(a.get("type", "COVER"), -1),
            *a.get("position", (0.0, 0.0)), float(a.get("channel", 0)),
            float(a.get("move_cost_s", 0.0)), float(a.get("measure_cost_s", 0.0)),
            float(a.get("switch_cost_s", 0.0)), float(a.get("certified_clear", False)),
            float(a.get("coverage_gain", 0.0)), float(a.get("localization_gain", 0.0)),
            float(a.get("probe_failure_cost_s", 0.0)),
        ] for a in candidates], dtype=np.float32) if candidates else np.zeros((0, 11), dtype=np.float32),
    }
