"""Public v3 feature schema with explicit action-to-channel/station binding."""
import math
import numpy as np
from solution.control.controller import STATES

FEATURE_VERSION = "normalized-public-v4-q4-belief-attention"
GLOBAL_DIM = 10
CHANNEL_DIM = 28
STATION_DIM = 8
CANDIDATE_DIM = 20
MAX_STATIONS = 31


def _channel_row(ctrl, channel, state):
    last = next((row for row in reversed(state.observations) if row["result"] == "direction"), None)
    theta = math.radians(last["svd_deg"]) if last else 0.0
    cert = state.cert
    center = cert["center"] if cert else (0.0, 0.0)
    area = float(state.region.geom.area) / 1e7
    belief=ctrl.q4_beliefs.get(channel)
    bs=belief.summary_at(ctrl.position) if belief else None
    belief_row=([float(bs.valid),bs.particle_count/256,bs.effective_sample_size/256,bs.age/40,
                 float(bs.degenerate),bs.reception_probability,bs.near_probability,bs.receive_entropy,
                 bs.directional_fraction,bs.dispersion/1800,bs.heading_sin,bs.heading_cos]
                if bs else [0.]*12)
    return [STATES.index(state.status) / 5, len(state.observations) / 50,
            math.sin(theta), math.cos(theta), center[0] / 2000, center[1] / 2000,
            area, cert["radius_upper_m"] / 1500 if cert else 1.0,
            len(state.covered_stations) / max(1, len(ctrl.stations)), state.localizations / 6,
            sum(row["result"] == "direction" for row in state.observations) / 20,
            sum(row["result"] == "no_signal" for row in state.observations) / 40,
            sum(tuple(row["position"]) == tuple(ctrl.position) for row in state.observations) / 10,
            float(state.status == "CLEARABLE"), float(channel == ctrl.current_channel),
            float(state.clear_attempts) / 10]+belief_row


def structural_features(ctrl, actions):
    global_row = np.asarray([
        ctrl.position[0] / 2000, ctrl.position[1] / 2000, ctrl.current_channel / 20,
        ctrl.virtual_time / 10000, getattr(ctrl, "remaining_real_s", 1200.) / 1200,
        len(ctrl.discovered) / 16, sum(s.status == "CLEARED" for s in ctrl.channels.values()) / 16,
        sum(s.status not in ("CLEARED", "ABSENT_CERTIFIED") for s in ctrl.channels.values()) / 20,
        ctrl.problem - 3, len(ctrl.physical_station_visited) / max(1, len(ctrl.stations))], dtype=np.float32)
    channels = np.asarray([_channel_row(ctrl, c, ctrl.channels[c]) for c in range(1, 21)], dtype=np.float32)
    stations = []
    for i, point in enumerate(ctrl.stations):
        missing = sum(ctrl.station_names[i] not in s.covered_stations and s.status == "UNKNOWN" for s in ctrl.channels.values())
        stations.append([point[0] / 2000, point[1] / 2000, float(i in ctrl.physical_station_visited),
                         missing / 20, math.dist(ctrl.position, point) / 4000,
                         float(i == ctrl.last_route.next_id), i / max(1, len(ctrl.stations)),
                         float(bool(ctrl._coverage_required(i)))])
    stations = np.asarray(stations, dtype=np.float32)
    rows = []
    channel_index, channel_valid, station_index, station_valid, scan_masks = [], [], [], [], []
    for action in actions:
        channel = int(action.channel or (action.channels[0] if action.channels else 0))
        cstate = ctrl.channels.get(channel)
        ci = channel - 1 if 1 <= channel <= 20 else 0
        mask = np.zeros(20, dtype=np.float32)
        for c in action.channels:
            if 1 <= c <= 20: mask[c - 1] = 1.0
        if not action.channels and 1 <= channel <= 20:
            mask[channel - 1] = 1.0
        station = int(action.station)
        related=tuple(action.channels) or ((channel,) if channel else ())
        summaries=[ctrl.q4_beliefs[c].summary_at(action.position) for c in related if c in ctrl.q4_beliefs]
        belief_candidate=([float(any(s.valid for s in summaries)),
                           float(np.mean([s.reception_probability for s in summaries])),
                           float(np.mean([s.near_probability for s in summaries])),
                           float(np.mean([s.receive_entropy for s in summaries])),
                           float(np.mean([s.directional_fraction for s in summaries])),
                           float(np.mean([s.dispersion for s in summaries]))/1800]
                          if summaries else [0.]*6)
        rows.append([{"COVER": 0, "LOCALIZE": 1, "CLEAR": 2, "PROBE_STEP": 3, "FULL_PROBE_FALLBACK": 4, "EXIT": 5}.get(action.kind, -1),
                     action.position[0] / 2000, action.position[1] / 2000, action.cost / 1000,
                     len(action.channels) / 20, float(channel == ctrl.current_channel),
                     float(bool(cstate is not None and cstate.status == "CLEARABLE")), float(action.kind == "COVER"),
                     float(action.kind == "PROBE_STEP"), action.route_rank / max(1, len(ctrl.stations)),
                     action.route_detour_m / 4000, float(action.kind == "FULL_PROBE_FALLBACK"),
                     float(action.kind == "EXIT"), float(action.kind == "LOCALIZE")]+belief_candidate)
        channel_index.append(ci); channel_valid.append(float(1 <= channel <= 20))
        station_index.append(station if 0 <= station < len(ctrl.stations) else 0)
        station_valid.append(float(0 <= station < len(ctrl.stations))); scan_masks.append(mask)
    return {"global": global_row, "channels": channels, "stations": stations,
            "station_mask": np.ones(len(stations), dtype=np.bool_),
            "candidates": np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, CANDIDATE_DIM), dtype=np.float32),
            "candidate_channel_index": np.asarray(channel_index, dtype=np.int64),
            "candidate_channel_valid": np.asarray(channel_valid, dtype=np.float32),
            "candidate_station_index": np.asarray(station_index, dtype=np.int64),
            "candidate_station_valid": np.asarray(station_valid, dtype=np.float32),
            "candidate_channel_mask": np.asarray(scan_masks, dtype=np.float32) if scan_masks else np.zeros((0, 20), dtype=np.float32)}
