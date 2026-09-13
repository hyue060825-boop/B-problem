class Blocked(RuntimeError):
    pass


def require_profile(profile):
    if profile == 'strict_official':
        raise Blocked('G01 G02 G03 G04 G05 G06 G07 G08 G09: official evidence unresolved; no fallback')
    if profile == 'compatible_research':
        raise Blocked('compatible_research is disabled: requires separately authorized assumptions and implementation')
    if profile != 'fixture_conformance':
        raise ValueError('unknown profile')
