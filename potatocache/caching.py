from functools import wraps
from django.core.cache import cache


def cached(
        key=None,
        arg_key=None,
        groups=None,
        debug=False,
    ):
    """Decorator caching with group caches."""
    def _decorator(func):
        @wraps(func)
        def wrapper(*a, **kw):
            # Check existing values in memcache
            value = cache.get(key)
            if value is None:
                if debug:
                    _inc_call_count(wrapper)
                value = func(*a, **kw)

                if value is None:
                    #TODO: Handle None values somehow
                    return None

                cache.set(key, value)
            return value
        return wrapper
    return _decorator


def _inc_call_count(func):
    if not hasattr(func, 'call_count'):
        setattr(func, 'call_count', 1)
    else:
        func.call_count += 1

