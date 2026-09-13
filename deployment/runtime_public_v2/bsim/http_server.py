"""Loopback transport, closed outside ready/entered lifecycle."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
from .protocol import encode, PATHS
from .session import InterfaceClosed


class LocalServer(ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, address, session):
        if address[0] != '127.0.0.1':
            raise ValueError('only 127.0.0.1 is supported')
        self.session = session
        self.delivery_lock = threading.Lock()
        self.delivery_active = None
        super().__init__(address, Handler)

    def service_actions(self):
        with self.session.condition:
            self.session.refresh()
        # Socket closure is managed by serve_session; tests may keep a bound
        # server whose handler closes unavailable connections (also documented).


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # Base parser errors also use public rejection shape.
        self.reply(*self.server.session.rejection(code))

    def reply(self, code, body):
        raw = encode(body)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)
        self.close_connection = True

    def handle_action(self):
        self.connection.settimeout(5)  # LOCAL incomplete-body resource guard, G07.
        session = self.server.session
        with session.condition:
            session.refresh()
            if session.phase not in ('ready', 'entered'):
                self.close_connection = True
                return
        try:
            if self.path not in PATHS:
                self.reply(*session.rejection(404))
                return
            if self.command != 'POST':
                self.reply(*session.rejection(405))
                return
            # Chunked/framing semantics not specified: reject instead of ambiguous parsing.
            if self.headers.get('Transfer-Encoding') is not None:
                self.reply(*session.rejection(400))
                return
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                self.reply(*session.rejection(400))
                return
            length = int(lengths[0])
            if length > 65536:
                self.reply(*session.rejection(413))
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.close_connection = True
                return
            fingerprint = (self.path, raw)
            with self.server.delivery_lock:
                owner = self.server.delivery_active is None
                conflict = not owner and self.server.delivery_active != fingerprint
                if owner:
                    self.server.delivery_active = fingerprint
            if conflict:
                self.reply(*session.rejection(409))
                return
            try:
                self.reply(*session.request(self.command, self.path, dict(self.headers), raw))
            finally:
                if owner:
                    with self.server.delivery_lock:
                        self.server.delivery_active = None
        except (InterfaceClosed, ConnectionError, socket.timeout, OSError):
            self.close_connection = True

    # All syntactically valid HTTP verbs must reach explicit 404/405 handling.
    def __getattr__(self, name):
        if name.startswith('do_'):
            return self.handle_action
        raise AttributeError(name)


def serve_session(session, host='127.0.0.1', port=2026):
    """Manager lifecycle: no listening socket until countdown has finished."""
    import time
    while session.phase in ('preparing', 'countdown'):
        session.refresh()
        time.sleep(.02)
    if session.phase not in ('ready', 'entered'):
        raise InterfaceClosed(session.phase)
    with LocalServer((host, port), session) as server:
        server.timeout = .05
        while True:
            with session.condition:
                session.refresh()
                ended = session.phase == 'ended' and session.active is None
            if ended:
                break
            server.handle_request()
