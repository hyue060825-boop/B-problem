"""Strategy-side client. Imports no scenario, evaluator or simulator state."""
import copy
import json
import threading
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from http.client import HTTPException
from .protocol import encode, finite, pairs

BASE_FIELDS = {'accepted', 'real_timestamp_ms', 'virtual_time_s'}
EXTRAS = {
    '/enter': {'max_virtual_duration_s', 'max_real_duration_s', 'remaining_real_duration_s'},
    '/measure': {'measure_result', 'svd_deg'},
    '/clear': {'clear_result'}, '/exit': {'exit_reason'},
}


def public_response(path, response, status=None):
    """先验证完整公开响应，再允许调用方更新状态。"""
    if not isinstance(path, str) or path not in EXTRAS or not isinstance(response, dict):
        raise ValueError('invalid response path or object')
    accepted = response.get('accepted')
    if type(accepted) is not bool:
        raise ValueError('invalid accepted')
    if status is not None:
        if type(status) is not int or not 100 <= status <= 599:
            raise ValueError('invalid HTTP status')
        if accepted and status != 200:
            raise ValueError('accepted action requires HTTP 200')
    required = set(BASE_FIELDS)
    if accepted:
        required |= EXTRAS[path]
        if path == '/measure' and response.get('measure_result') != 'direction':
            required -= {'svd_deg'}
    if response.keys() != required:
        raise ValueError('missing or unexpected robot response fields')
    for field in ('real_timestamp_ms', 'virtual_time_s'):
        if not finite(response[field]) or response[field] < 0:
            raise ValueError('invalid ' + field)
    if not accepted:
        if response['virtual_time_s'] != 0:
            raise ValueError('rejection clock must be zero')
    elif path == '/enter':
        for field in ('max_virtual_duration_s', 'max_real_duration_s'):
            if not finite(response[field]) or response[field] <= 0:
                raise ValueError('invalid ' + field)
        remaining = response['remaining_real_duration_s']
        if (not finite(remaining) or remaining != int(remaining)
                or not 0 <= remaining <= min(1200, response['max_real_duration_s'])):
            raise ValueError('invalid remaining_real_duration_s')
        if response['virtual_time_s'] != 0:
            raise ValueError('enter virtual time must be zero')
    elif path == '/measure':
        if response['measure_result'] not in ('direction', 'near', 'no_signal'):
            raise ValueError('invalid measure_result')
        if response['measure_result'] == 'direction':
            angle = response['svd_deg']
            if not finite(angle) or not 0 <= angle < 360:
                raise ValueError('invalid svd_deg')
    elif path == '/clear':
        if response['clear_result'] not in ('success', 'no_target_in_range'):
            raise ValueError('invalid clear_result')
    elif response['exit_reason'] != 'user_exit':
        raise ValueError('invalid exit_reason')
    return copy.deepcopy(response)


class RobotClient:
    def __init__(self, base_url, robot_id, timeout=5, retries=2, transport=None):
        url = urlsplit(base_url)
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path not in ('', '/') or url.query or url.fragment or url.username:
            raise ValueError('client must use loopback HTTP')
        self.base_url, self.robot_id, self.timeout, self.retries = base_url.rstrip('/'), robot_id, timeout, retries
        self._transport = transport or self._http
        self._lock = threading.Lock()
        self._history = []
        self.virtual_time_s = 0
        self._pending = None

    def _http(self, path, raw):
        req = Request(self.base_url + path, data=raw, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(req, timeout=self.timeout) as res:
                return res.status, json.loads(res.read(), object_pairs_hook=pairs)
        except HTTPError as res:
            return res.code, json.loads(res.read(), object_pairs_hook=pairs)

    def act(self, path, position=None, channel=None):
        with self._lock:
            if self._pending is not None:
                raise RuntimeError('ambiguous previous outcome: use retry_pending(), never send a new action')
            if path not in EXTRAS:
                raise ValueError('only four official actions')
            data = {'arena_id': 'default', 'robot_id': self.robot_id, 'request_id': str(uuid.uuid4())}
            if position is not None:
                data['position'] = {'x': position[0], 'y': position[1]}
            if channel is not None:
                data['channel'] = channel
            self._pending = (path, encode(data))
            return self._send_pending()

    def retry_pending(self):
        with self._lock:
            if self._pending is None:
                raise RuntimeError('no pending action')
            return self._send_pending()

    def _send_pending(self):
        path, raw = self._pending
        for attempt in range(self.retries + 1):
            try:
                code, body = self._transport(path, raw)
                body = public_response(path, body, code)
                # Do not count a replay twice in local history.
                self._history.append({'path': path, 'request': json.loads(raw), 'status': code, 'response': body})
                if code == 200 and body['accepted']:
                    self.virtual_time_s = body['virtual_time_s']
                self._pending = None
                return code, copy.deepcopy(body)
            except (URLError, OSError, HTTPException):
                if attempt == self.retries:
                    raise

    def history(self):
        return copy.deepcopy(self._history)

    def actor_input(self):
        return {'history': self.history(), 'virtual_time_s': self.virtual_time_s}
