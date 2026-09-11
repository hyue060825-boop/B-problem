"""Observable-history controller and deterministic fallback scheduler."""
from dataclasses import dataclass, field
import math
from solution.geometry.core import FeasibleRegion
from solution.coverage.certificates import omni_skeleton, triangular_grid


STATES = ("UNKNOWN", "FOUND", "LOCALIZING", "CLEARABLE", "CLEARED", "ABSENT_CERTIFIED")


@dataclass
class ChannelState:
    status: str = "UNKNOWN"
    observations: list = field(default_factory=list)
    region: FeasibleRegion = field(default_factory=FeasibleRegion)
    covered_stations: set = field(default_factory=set)
    clear_attempts: int = 0
    near_position: tuple | None = None


class Controller:
    """Rule-first controller. It never receives scenario truth or N.

    `next_action` returns one official bottom-level action tuple. Any macro
    scheduling or RL policy can rank these same legal candidates.
    """
    def __init__(self, problem=3, epsilon_deg=1.01):
        if problem not in (3, 4):
            raise ValueError("problem must be 3 or 4")
        self.problem = problem
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.channels = {c: ChannelState(region=FeasibleRegion(epsilon_deg)) for c in range(1, 21)}
        self.discovered = set()
        self.stations = omni_skeleton()[0] if problem == 3 else triangular_grid()["vertices"]
        self.station_index = 0
        self.covered = {c: set() for c in range(1, 21)}

    def observe(self, channel, position, result, svd_deg=None, station=None):
        if channel not in self.channels:
            raise ValueError("channel")
        state = self.channels[channel]
        self.position = tuple(position)
        state.observations.append({"position": list(position), "result": result, "svd_deg": svd_deg})
        if station is not None:
            state.covered_stations.add(station)
        if result == "near":
            state.status = "CLEARABLE"
            state.near_position = tuple(position)
        elif result == "direction":
            self.discovered.add(channel)
            state.status = "LOCALIZING"
            state.region.direction(position, svd_deg)
            if state.region.certificate()["safe"]:
                state.status = "CLEARABLE"
        elif result == "no_signal" and state.status == "UNKNOWN":
            # Q3 can use a station's 1000 m coverage only when this channel
            # itself was tested there. Q4 never treats no_signal as distance.
            if self.problem == 3 and station is not None:
                state.region.exclude(position, 1000.0)
        return state.status

    def candidates(self):
        out = []
        for channel, state in self.channels.items():
            if state.status == "CLEARABLE":
                if state.near_position is not None:
                    out.append(("/clear", state.near_position, channel, "near_immediate_clear"))
                    continue
                cert = state.region.certificate()
                if cert and cert["safe"]:
                    out.append(("/clear", tuple(cert["center"]), channel, "certified_clear"))
                else:
                    try:
                        for q in state.region.clear_cover()[:3]:
                            out.append(("/clear", tuple(q), channel, "probe_clear"))
                    except (RuntimeError, ValueError):
                        pass
            elif state.status in ("LOCALIZING", "FOUND"):
                cert = state.region.certificate()
                if cert:
                    out.append(("/measure", tuple(cert["center"]), channel, "localize"))
        # A deterministic safety action takes precedence over discovering new
        # channels; the caller may still rank among these clear candidates.
        if out:
            return out
        if self.problem == 3:
            while self.station_index < len(self.stations):
                key, q = list(self.stations.items())[self.station_index]
                self.station_index += 1
                missing = [c for c,s in self.channels.items() if s.status == "UNKNOWN"]
                if missing:
                    return [("/measure", q, c, "cover") for c in missing]
        else:
            while self.station_index < len(self.stations):
                q = self.stations[self.station_index]; self.station_index += 1
                missing = [c for c,s in self.channels.items() if s.status == "UNKNOWN"]
                if missing:
                    return [("/measure", q, c, "directional_cover") for c in missing]
        return out

    def next_action(self):
        options = self.candidates()
        if not options:
            if all(s.status in ("CLEARED", "ABSENT_CERTIFIED") for s in self.channels.values()):
                return ("/exit", None, None, "certified_exit")
            # No legal progress candidate: expose recovery instead of looping.
            return None
        # Deterministic cost first; ties preserve channel continuity.
        options.sort(key=lambda a: (math.dist(self.position, a[1]) if a[1] else 0,
                                    a[2] != self.current_channel if a[2] else False))
        return options[0]

    def clear_result(self, channel, success):
        state = self.channels[channel]
        state.clear_attempts += 1
        if success:
            state.status = "CLEARED"
        return state.status

    def certify_absent(self, channel):
        """Q3 only: mark absent after this channel's own station coverage."""
        state = self.channels[channel]
        if self.problem != 3:
            raise ValueError("Q4 no_signal cannot certify absence")
        required = set(self.stations)
        if required <= state.covered_stations and not self.discovered.intersection({channel}):
            state.status = "ABSENT_CERTIFIED"
        return state.status

    def mark_all_remaining_absent_after_16(self):
        if len(self.discovered) >= 16:
            for state in self.channels.values():
                if state.status == "UNKNOWN":
                    state.status = "ABSENT_CERTIFIED"

    def exit_allowed(self):
        return all(s.status in ("CLEARED", "ABSENT_CERTIFIED") for s in self.channels.values())
