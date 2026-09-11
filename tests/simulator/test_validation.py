"""异常输入、客户端恢复和轨迹核对的回归。"""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from bsim.client import RobotClient, public_response
from bsim.evaluation import audit_public_trace, replay
from bsim.protocol import encode
from bsim.source_audit import audit_sources
from tests.simulator.support import HEADERS, ROOT, call, make, payload


class Validation(unittest.TestCase):
    def setUp(self):
        self.records = replay(
            ROOT / 'tests/fixtures/simulator/timing.json',
            ROOT / 'tests/fixtures/simulator/timing.trace.json')['records']

    def test_required_response_fields_and_numeric_ranges(self):
        for row in self.records:
            for field in row['response']:
                body = copy.deepcopy(row['response'])
                del body[field]
                with self.subTest(path=row['path'], missing=field), self.assertRaises(ValueError):
                    public_response(row['path'], body, 200)
        base = {'accepted': True, 'real_timestamp_ms': 0, 'virtual_time_s': 5}
        for field in ('real_timestamp_ms', 'virtual_time_s'):
            for value in (True, 'oops', None, -1, float('nan'), float('inf')):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    public_response('/measure', {**base, 'measure_result': 'near', field: value})
        for value in (True, '10', -0.01, 360, 400, float('nan')):
            with self.subTest(angle=value), self.assertRaises(ValueError):
                public_response('/measure', {**base, 'measure_result': 'direction', 'svd_deg': value})
        for value in (0, 359.99):
            public_response('/measure', {**base, 'measure_result': 'direction', 'svd_deg': value})
        for value in (-1, 0.5, 1201, True):
            body = {**self.records[0]['response'], 'remaining_real_duration_s': value}
            with self.subTest(remaining=value), self.assertRaises(ValueError):
                public_response('/enter', body)

    def test_result_enums_and_http_acceptance(self):
        for path, field in [('/clear', 'clear_result'), ('/exit', 'exit_reason'),
                            ('/measure', 'measure_result')]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                public_response(path, {'accepted': True, 'real_timestamp_ms': 0,
                                       'virtual_time_s': 5, field: 'unexpected'})
        body = self.records[1]['response']
        for status in (500, True, '200'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                public_response('/measure', body, status)
        with self.assertRaises(ValueError):
            public_response('/measure', [])
        rejected = {'accepted': False, 'real_timestamp_ms': 0, 'virtual_time_s': 0}
        public_response('/measure', rejected, 400)
        with self.assertRaises(ValueError):
            public_response('/measure', {**rejected, 'virtual_time_s': 1}, 400)

    def test_malformed_response_keeps_pending_and_retry_does_not_double_execute(self):
        session = make()
        seen = []
        broken = [True]
        def transport(path, raw):
            seen.append(raw)
            status, body = session.request('POST', path, HEADERS, raw)
            if path == '/measure' and broken[0]:
                broken[0] = False
                body = {**body, 'virtual_time_s': 'oops'}
            return status, body
        client = RobotClient('http://127.0.0.1:1', 'LOCAL-TEAM', transport=transport)
        client.act('/enter')
        with self.assertRaises(ValueError):
            client.act('/measure', (300, 400), 1)
        self.assertEqual(client.virtual_time_s, 0)
        self.assertEqual(len(client.history()), 1)
        with self.assertRaises(RuntimeError):
            client.act('/exit')
        self.assertEqual(client.retry_pending()[1]['virtual_time_s'], 105)
        self.assertEqual(seen[-1], seen[-2])
        self.assertEqual(session.state.virtual_us, 105000000)
        self.assertEqual(len(session.events), 2)
        self.assertEqual(len(client.history()), 2)

    def test_deep_json_is_rejected_without_recursion_error(self):
        session = make()
        call(session, '/enter', 'enter')
        before = session.state
        data = payload('deep', (0, 0), 1)
        value = 0
        for _ in range(600):
            value = {'x': value}
        data['extra'] = value
        self.assertEqual(session.request('POST', '/measure', HEADERS, encode(data))[0], 400)
        self.assertEqual(session.state, before)
        self.assertNotIn('deep', session.cache)

    def test_trace_rejects_malformed_responses_and_invalid_order(self):
        mutations = [
            lambda r: r[3]['response'].__setitem__('clear_result', 'unexpected'),
            lambda r: r[0]['response'].pop('remaining_real_duration_s'),
            lambda r: r[-1]['response'].__setitem__('real_timestamp_ms', float('nan')),
            lambda r: r[1].__setitem__('status', 500),
            lambda r: r[1].__setitem__('path', []),
            lambda r: r[1]['request']['position'].__setitem__('x', True),
        ]
        for mutation in mutations:
            rows = copy.deepcopy(self.records)
            mutation(rows)
            self.assertEqual(audit_public_trace(rows)['status'], 'FAIL')
        enter = copy.deepcopy(self.records[0])
        enter['request']['request_id'] = 'another-enter'
        self.assertEqual(audit_public_trace(self.records[:1] + [enter] + self.records[1:])['status'], 'FAIL')
        action = copy.deepcopy(self.records[1])
        action['request']['request_id'] = 'after-exit'
        self.assertEqual(audit_public_trace(self.records + [action])['status'], 'FAIL')

    def test_trace_marks_partial_or_unconfirmed_records_incomplete(self):
        for rows in ([], self.records[1:], self.records[:-1]):
            report = audit_public_trace(rows)
            self.assertEqual(report['status'], 'INCOMPLETE')
            self.assertTrue(report['unverified'])
        missing = copy.deepcopy(self.records[1])
        missing['status'] = missing['response'] = None
        rows = self.records[:1] + [missing] + self.records[2:]
        self.assertEqual(audit_public_trace(rows)['status'], 'INCOMPLETE')

    def test_trace_recovers_lost_response_and_deduplicates_replays(self):
        missing = copy.deepcopy(self.records[1])
        missing['status'] = missing['response'] = None
        rows = self.records[:1] + [missing] + self.records[1:2] + self.records[1:]
        report = audit_public_trace(rows)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['checked_transitions'], 4)
        self.assertEqual(report['unverified'], [])

    def test_source_audit_detects_changes_missing_and_invalid_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / '原件.txt'
            source.write_bytes(b'original')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / 'SHA256SUMS'
            manifest.write_text(digest + '  原件.txt\n', encoding='utf-8')
            self.assertEqual(audit_sources(root)['status'], 'PASS')
            source.write_bytes(b'changed')
            self.assertEqual(audit_sources(root)['sources'][0]['status'], 'CHANGED_REVIEW_REQUIRED')
            source.unlink()
            self.assertEqual(audit_sources(root)['sources'][0]['status'], 'MISSING')
            for contents in ('', 'bad line', digest + '  ../outside\n'):
                manifest.write_text(contents, encoding='utf-8')
                with self.assertRaises(ValueError):
                    audit_sources(root)
