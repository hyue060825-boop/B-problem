"""LOCAL management UI on a separate authenticated port; not a robot endpoint."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .client import RobotClient
from .clocks import SystemClock
from .http_server import serve_session
from .protocol import encode
from .reference import ReferenceKernel
from .scenarios import load_fixture
from .session import Session, InterfaceClosed
from .paths import FIXTURES as FIXTURE_DIR

ASSETS = Path(__file__).with_name('web')
FIXTURES = {'timing': FIXTURE_DIR / 'timing.json', 'mixed': FIXTURE_DIR / 'visual_mixed.json'}


class Dashboard:
    def __init__(self, robot_port=20260):
        if not 1 <= robot_port <= 65535:
            raise ValueError('invalid robot port')
        self.robot_port = robot_port
        self.lock = threading.RLock()
        self.action_lock = threading.Lock()
        self.session = None
        self.session_id = None
        self.worker = None
        self.client = None
        self.error = None
        self.fixture_key = None

    def start(self, fixture):
        if fixture not in FIXTURES:
            raise ValueError('unknown fixture')
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError('当前会话尚未关闭，请结束后再开始。')
            # Fail before countdown if an official or other service owns the port.
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(('127.0.0.1', self.robot_port))
            data, scenario, noise, numerics = load_fixture(FIXTURES[fixture])
            session = Session(ReferenceKernel(scenario, noise, numerics), SystemClock(), data['robot_id'])
            session.prepare()
            session.data_ready()
            self.session, self.session_id = session, secrets.token_hex(8)
            self.fixture_key, self.error = fixture, None
            self.client = RobotClient('http://127.0.0.1:%d' % self.robot_port, data['robot_id'], timeout=2, retries=1)
            self.worker = threading.Thread(target=self._serve, args=(session,), daemon=True)
            self.worker.start()
            return self.snapshot()

    def _serve(self, session):
        try:
            serve_session(session, port=self.robot_port)
        except InterfaceClosed:
            pass
        except Exception as exc:
            with self.lock:
                self.error = '本地动作服务启动/运行失败：%s' % exc
            session.abort()

    def check_session(self, session_id):
        if self.session is None or self.session_id != session_id:
            raise ValueError('会话已变化，请刷新状态后重试。')

    def abort(self, session_id):
        with self.lock:
            self.check_session(session_id)
            self.session.abort()
            return self.snapshot()

    def action(self, data):
        if not self.action_lock.acquire(blocking=False):
            raise ValueError('上一个动作尚未完成。')
        try:
            with self.lock:
                self.check_session(data.get('session_id'))
                client = self.client
            if data.get('action') == 'retry':
                status, response = client.retry_pending()
            else:
                name = data.get('action')
                if name not in ('enter', 'measure', 'clear', 'exit'):
                    raise ValueError('unknown action')
                position = data.get('position')
                if name in ('measure', 'clear') and (not isinstance(position, list) or len(position) != 2):
                    raise ValueError('position must contain x,y')
                status, response = client.act('/' + name, position, data.get('channel'))
            return {'status': status, 'response': response}
        finally:
            self.action_lock.release()

    def snapshot(self):
        with self.lock:
            s = self.session
            base = {'label': 'LOCAL-dashboard', 'session_id': self.session_id, 'fixture': self.fixture_key,
                    'robot_url': 'http://127.0.0.1:%d' % self.robot_port,
                    'robot_id': 'LOCAL-TEAM', 'error': self.error,
                    'service_running': bool(self.worker and self.worker.is_alive())}
            if s is None:
                return {**base, 'phase': 'idle', 'events': [], 'position': [0, 0], 'channel': 1,
                        'virtual_time_s': 0, 'cleared_count': 0, 'countdown_s': 0, 'remaining_real_s': None,
                        'window_remaining_s': None, 'reason': None, 'pending': False}
            with s.condition:
                s.refresh()
                now = s.clock.monotonic()
                # Only public accepted action/response records; never serialize kernel.
                events = [{'path': e['path'], 'request': copy.deepcopy(e['request']),
                           'response': copy.deepcopy(e['response']), 'status': 200} for e in s.events]
                return {**base, 'phase': s.phase, 'events': events[-1000:], 'event_total': len(events),
                        'position': list(s.state.position), 'channel': s.state.channel,
                        'virtual_time_s': s.state.virtual_us / 1000000,
                        'cleared_count': sum(e['response'].get('clear_result') == 'success' for e in events),
                        'countdown_s': max(0, (s.countdown_end or now) - now) if s.phase == 'countdown' else 0,
                        'remaining_real_s': max(0, s.deadline() - now) if s.window_open is not None and s.phase != 'ended' else None,
                        'window_remaining_s': max(0, s.window_open + 1500 - now) if s.window_open is not None and s.phase != 'ended' else None,
                        'reason': s.reason, 'pending': self.client._pending is not None,
                        'error': self.error or s.last_error}

    def truth(self):
        with self.lock:
            if self.session is None:
                return {'label': 'LOCAL-admin-truth', 'sources': []}
            with self.session.condition:
                return {'label': 'LOCAL-admin-truth', 'session_id': self.session_id,
                        'sources': [{**asdict(s), 'cleared': s.channel in self.session.state.cleared}
                                    for s in self.session.kernel.scenario.sources]}

    def export(self):
        with self.lock:
            if self.session is None:
                raise ValueError('暂无会话记录。')
            with self.session.condition:
                return {'label': 'LOCAL-web-trace', 'records': [
                    {'path': e['path'], 'request': copy.deepcopy(e['request']), 'status': 200,
                     'response': copy.deepcopy(e['response'])} for e in self.session.events],
                    'note': 'Accepted actions only; LOCAL public trace, not official encrypted log.'}

    def close(self):
        with self.lock:
            if self.session:
                self.session.abort()
            worker = self.worker
        if worker:
            worker.join(7)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, manager, token=None):
        if address[0] != '127.0.0.1':
            raise ValueError('dashboard binds loopback only')
        self.manager, self.token = manager, token or secrets.token_urlsafe(32)
        super().__init__(address, DashboardHandler)


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log administrator access token.

    def respond(self, status, value, content_type='application/json; charset=utf-8'):
        body = value if isinstance(value, bytes) else encode(value)
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        value = self.headers.get('Authorization', '')
        if not secrets.compare_digest(value.encode('utf-8'), ('Bearer ' + self.server.token).encode('utf-8')):
            self.respond(401, {'error': '需要本地管理访问密钥，请打开启动命令给出的完整链接。'})
            return False
        origin = self.headers.get('Origin')
        expected = 'http://127.0.0.1:%d' % self.server.server_address[1]
        if origin and origin != expected:
            self.respond(403, {'error': '跨来源管理请求被拒绝。'})
            return False
        return True

    def do_GET(self):
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path in assets:
            name, mime = assets[self.path]
            self.respond(200, (ASSETS / name).read_bytes(), mime)
            return
        if not self.path.startswith('/api/'):
            self.respond(404, {'error': 'Not found'})
            return
        if not self.authorized():
            return
        try:
            routes = {'/api/state': self.server.manager.snapshot, '/api/debug/truth': self.server.manager.truth,
                      '/api/export': self.server.manager.export}
            if self.path not in routes:
                self.respond(404, {'error': 'Not found'})
                return
            self.respond(200, routes[self.path]())
        except ValueError as exc:
            self.respond(400, {'error': str(exc)})

    def do_POST(self):
        if not self.authorized():
            return
        try:
            self.connection.settimeout(5)
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= 4096:
                raise ValueError('invalid body length')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON required')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
            if self.path == '/api/start':
                result = self.server.manager.start(data.get('fixture'))
            elif self.path == '/api/abort':
                result = self.server.manager.abort(data.get('session_id'))
            elif self.path == '/api/action':
                result = self.server.manager.action(data)
            else:
                self.respond(404, {'error': 'Not found'})
                return
            self.respond(200, result)
        except (ValueError, OSError, RuntimeError) as exc:
            self.respond(400, {'error': str(exc)})


def serve_dashboard(port=8765, robot_port=20260):
    if port == robot_port:
        raise ValueError('管理网页和动作接口必须使用不同端口。')
    manager = Dashboard(robot_port)
    with DashboardServer(('127.0.0.1', port), manager) as server:
        print('LOCAL management dashboard: http://127.0.0.1:%d/#token=%s' % (server.server_address[1], server.token), flush=True)
        print('Robot actions use 127.0.0.1:%d after starting a fixture and countdown.' % robot_port, flush=True)
        try:
            server.serve_forever(poll_interval=.1)
        except KeyboardInterrupt:
            pass
        finally:
            manager.close()
