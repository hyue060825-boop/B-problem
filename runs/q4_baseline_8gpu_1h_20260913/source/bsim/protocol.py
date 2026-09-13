"""Raw validation. Composite-error precedence is LOCAL policy (G07)."""
import json
import math
import unicodedata

PATHS = {'/enter', '/measure', '/clear', '/exit'}
COMMON = {'arena_id', 'robot_id', 'request_id'}


class Invalid(ValueError):
    def __init__(self, status):
        self.status = status


def identifier(value, limit):
    if not isinstance(value, str):
        raise Invalid(400)
    try:
        length = len(value.encode('utf-8'))
    except UnicodeError:
        raise Invalid(400)
    if not 1 <= length <= limit or any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs') for c in value):
        raise Invalid(400)


def pairs(items):
    result = {}
    for key, val in items:
        if key in result:
            raise Invalid(400)
        result[key] = val
    return result


def depth(value):
    # TEST convention: root object is depth 1, scalar does not add depth.
    if isinstance(value, dict):
        return 1 + max((depth(x) for x in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((depth(x) for x in value), default=0)
    return 0


def finite(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except OverflowError:
        return False


def validate(method, path, headers, body, robot_id):
    if path not in PATHS:
        raise Invalid(404)
    if method != 'POST':
        raise Invalid(405)
    h = {k.lower(): v for k, v in headers.items()}
    content = [s.strip().lower() for s in h.get('content-type', '').split(';')]
    if content not in (['application/json'], ['application/json', 'charset=utf-8']) or h.get('content-encoding', 'identity').lower() != 'identity':
        raise Invalid(415)
    if len(body) > 65536:
        raise Invalid(413)
    if body.startswith(b'\xef\xbb\xbf'):
        raise Invalid(400)
    try:
        data = json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid(400)))
    except (ValueError, UnicodeError, RecursionError):
        raise Invalid(400)
    if not isinstance(data, dict) or depth(data) > 16:
        raise Invalid(400)
    required = COMMON | ({'position', 'channel'} if path in ('/measure', '/clear') else set())
    if not required <= data.keys():
        raise Invalid(400)
    identifier(data['robot_id'], 64)
    identifier(data['request_id'], 128)
    if not isinstance(data['arena_id'], str):
        raise Invalid(400)
    try:
        data['arena_id'].encode('ascii')
    except UnicodeError:
        raise Invalid(400)
    unknown = data.keys() - required
    if 'position' in required:
        p, c = data['position'], data['channel']
        if not isinstance(p, dict) or not {'x', 'y'} <= p.keys():
            raise Invalid(400)
        if not all(finite(p[k]) and abs(p[k]) <= 2000000 for k in ('x', 'y')):
            raise Invalid(400)
        if not finite(c) or c != int(c) or not 1 <= c <= 20:
            raise Invalid(400)
        unknown |= p.keys() - {'x', 'y'}
    if unknown or data['arena_id'] != 'default' or data['robot_id'] != robot_id:
        raise Invalid(200)
    return data


def encode(body):
    return json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
