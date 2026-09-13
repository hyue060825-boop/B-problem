"""Strategy-side client. Imports no scenario, evaluator or simulator state."""
import copy
import json
import threading
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from http.client import HTTPException
from .protocol import encode

BASE_FIELDS = {'accepted', 'real_timestamp_ms', 'virtual_time_s'}
EXTRAS = {
    '/enter': {'max_virtual_duration_s', 'max_real_duration_s', 'remaining_real_duration_s'},
    '/measure': {'measure_result', 'svd_deg'},
    '/clear': {'clear_result'}, '/exit': {'exit_reason'},
}


def public_response(path, response):
    allowed = BASE_FIELDS | (EXTRAS[path] if response.get('accepted') is True else set())
    if not BASE_FIELDS <= response.keys() or response.keys() - allowed:
        raise ValueError('unexpected robot response fields')
    if type(response['accepted']) is not bool:
        raise ValueError('invalid accepted')
    if response.get('accepted') and path == '/measure':
        if response.get('measure_result') not in ('direction', 'near', 'no_signal'):
            raise ValueError('measure_result')
        if ('svd_deg' in response) != (response['measure_result'] == 'direction'):
            raise ValueError('direction field mismatch')
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
                return res.status, json.loads(res.read())
        except HTTPError as res:
            return res.code, json.loads(res.read())

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
                body = public_response(path, body)
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
