"""One session, serialized atomic commit. No hidden state enters responses."""
import copy
import math
import threading
from .reference import State
from .protocol import Invalid, validate, identifier


class InterfaceClosed(ConnectionError):
    pass


class Session:
    def __init__(self, kernel, clock, robot_id, cache_capacity=None):
        identifier(robot_id, 64)
        if cache_capacity is not None and (type(cache_capacity) is not int or cache_capacity < 1):
            raise ValueError('TEST capacity')
        self.kernel, self.clock, self.robot_id = kernel, clock, robot_id
        self.state = State()
        self.phase = 'idle'
        self.window_open = self.entered_at = self.countdown_end = None
        self.reason = None
        self.cache = {}
        self.cache_capacity = cache_capacity  # None means no invented official threshold.
        self.condition = threading.Condition()
        self.active = None
        self.last_error = None  # ADMIN only
        self.events = []  # ADMIN only

    def prepare(self):
        if self.phase != 'idle':
            raise ValueError('cannot reset a session')
        self.phase = 'preparing'

    def data_ready(self):
        if self.phase != 'preparing':
            raise ValueError('not preparing')
        self.phase = 'countdown'
        self.countdown_end = self.clock.monotonic() + 5

    def ready_fixture(self):
        """Explicit manager shortcut, no fifth robot endpoint."""
        self.prepare()
        self.data_ready()
        self.countdown_end = self.clock.monotonic()
        self.refresh()

    def deadline(self):
        if self.window_open is None:
            return math.inf
        return min(self.window_open + 1500, self.entered_at + 1200 if self.entered_at is not None else math.inf)

    def refresh(self):
        now = self.clock.monotonic()
        if self.phase == 'countdown' and now >= self.countdown_end:
            self.window_open = self.countdown_end
            self.phase = 'ready'
        if self.active is None and self.phase in ('ready', 'entered') and now >= self.deadline():
            self.phase, self.reason = 'ended', 'real_timeout'
        if self.active is None and self.phase == 'entered' and self.state.virtual_us >= 360000000000:
            self.phase, self.reason = 'ended', 'virtual_timeout'

    def abort(self):
        with self.condition:
            # An already registered action is permitted to finish.
            self.phase, self.reason = 'ended', 'manual_abort'

    def rejection(self, status):
        return status, {'accepted': False, 'real_timestamp_ms': self.clock.timestamp_ms(), 'virtual_time_s': 0}

    def request(self, method, path, headers, body):
        with self.condition:
            self.refresh()
            if self.phase not in ('ready', 'entered'):
                raise InterfaceClosed(self.reason or self.phase)
        try:
            data = validate(method, path, headers, body, self.robot_id)
        except Invalid as err:
            return self.rejection(err.status)
        rid = data['request_id']
        fingerprint = (path, body)  # exact-byte TEST policy, G07
        with self.condition:
            self.refresh()
            if self.phase not in ('ready', 'entered'):
                raise InterfaceClosed(self.reason or self.phase)
            if rid in self.cache:
                old, response = self.cache[rid]
                return copy.deepcopy(response) if old == fingerprint else self.rejection(409)
            if self.active is not None:
                if self.active != (rid, fingerprint):
                    return self.rejection(409)
                # LOCAL same-ID in-flight merge policy; G07 not claimed resolved.
                while self.active is not None:
                    self.condition.wait()
                if rid in self.cache:
                    return copy.deepcopy(self.cache[rid][1])
                return self.rejection(500)
            if (path == '/enter' and self.phase != 'ready') or (path != '/enter' and self.phase != 'entered'):
                return self.rejection(200)
            if self.cache_capacity is not None and len(self.cache) >= self.cache_capacity:
                return self.rejection(429)
            if self.clock.monotonic() >= self.deadline():
                self.phase, self.reason = 'ended', 'real_timeout'
                raise InterfaceClosed(self.reason)
            self.active = (rid, fingerprint)
            registered_at = self.clock.monotonic()
            old_state = self.state
        try:
            extra = {}
            new_state = old_state
            if path == '/enter':
                extra = {'max_virtual_duration_s': 360000, 'max_real_duration_s': 1200,
                         'remaining_real_duration_s': max(0, min(1200, math.floor(self.window_open + 1500 - registered_at)))}
            elif path == '/exit':
                extra = {'exit_reason': 'user_exit'}
            else:
                p = (data['position']['x'], data['position']['y'])
                new_state, extra = self.kernel.transition(old_state, path, p, int(data['channel']))
            us = new_state.virtual_us
            response = (200, {'accepted': True, 'real_timestamp_ms': self.clock.timestamp_ms(),
                              'virtual_time_s': us // 1000000 if us % 1000000 == 0 else us / 1000000, **extra})
            with self.condition:
                self.state = new_state
                if path == '/enter':
                    self.entered_at = registered_at
                    if self.phase != 'ended':
                        self.phase = 'entered'
                elif path == '/exit':
                    self.phase, self.reason = 'ended', 'user_exit'
                self.cache[rid] = (fingerprint, copy.deepcopy(response))
                self.events.append({'path': path, 'request': copy.deepcopy(data), 'response': copy.deepcopy(response[1]),
                                    'registered_at': registered_at})
            return response
        except Exception as err:
            # Physical computation is pure: failure cannot partially move or clear.
            self.last_error = '%s: %s' % (type(err).__name__, err)
            return self.rejection(500)
        finally:
            with self.condition:
                self.active = None
                self.refresh()
                self.condition.notify_all()
