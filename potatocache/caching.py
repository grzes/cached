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
            assert bool(key) != bool(arg_key), "You need to provide a key or an arg_key"
            _key = arg_key % a if key is None else key
            # Check existing values in memcache
            value = cache.get(_key)
            if value is None:
                if debug:
                    _inc_call_count(wrapper)
                value = func(*a, **kw)

                if value is None:
                    #TODO: Handle None values somehow
                    return None

                cache.set(_key, value)
            return value
        return wrapper
    return _decorator


def expire_group(*group_names):
    pass


def _inc_call_count(func):
    if not hasattr(func, 'call_count'):
        setattr(func, 'call_count', 1)
    else:
        func.call_count += 1

