"""Manager-owned batch. Returned actor inputs are official responses only.

For an untrusted/production actor use HTTP in a separate process. Python object
encapsulation within one process is not a security sandbox.
"""
from .protocol import encode
from .client import public_response
from .session import InterfaceClosed


class BatchEnv:
    def __init__(self, sessions):
        self._sessions = list(sessions)

    def step(self, requests):
        if len(requests) != len(self._sessions):
            raise ValueError('one request per independent session')
        output = []
        for session, (path, data) in zip(self._sessions, requests):
            try:
                code, body = session.request('POST', path, {'Content-Type': 'application/json'}, encode(data))
                output.append({'status': code, 'response': public_response(path, body), 'connection_closed': False})
            except InterfaceClosed:
                output.append({'status': None, 'response': None, 'connection_closed': True})
        return output
