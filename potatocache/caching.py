import uuid
from functools import wraps
from django.core.cache import cache

# Ideally we want to cache the value forever and rely on invalidation, # but this is not supported by django
# (https://code.djangoproject.com/ticket/9595). We could use memcache directly, but then we have to be careful to
# handle versioning as well. For now, just setting it to very far in the future.
VERY_LONG_TIME = 60*60*24*30*365  # a year


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
            keys = [arg_key % a] if key is None else [key]
            keys.extend(groups)  # ! the rest of the code relies on the group keys being equal to their names!

            re_evaluate = False
            # Check existing values in memcache
            multi_result = cache.get_many(keys)
            cache_value = multi_result.pop(key, None)
            # If any of the group markers is missing - regenerate it.
            marker_values = {g: v or _make_marker_value() for g, v in multi_result.iteritems()}

            # The cache should be a dict of {"value": <actual_func_value>, "group1": <marker1>, "group2": <marker2>, ...}
            if cache_value is None or type(cache_value) is not dict or 'value' not in cache_value:
                # The cached value itself is missing, or something else overwrote it?
                re_evaluate = True
            else:
                # Check if any of the groups changed since this value was cached
                for group, value in marker_values.iteritems():
                    if value != cache_value.get(group, None):
                        re_evaluate = True

            if re_evaluate:
                if debug: _inc_call_count(wrapper)
                value = func(*a, **kw)

                cache_value = dict(marker_values)
                cache_value['value'] = value

                # Store the regenerated value in the cache. Storing the markers as well, because since memcache will evict
                # keys on a LRU basis, we want to make sure the group keys get 'touched' whenever a value belonging to them
                # is cached.
                marker_values[key] = cache_value
                cache.set_many(marker_values, timeout=VERY_LONG_TIME)

            else:
                value = cache_value['value']

            return value
        return wrapper
    return _decorator


def expire_group(*group_names):
    cache.set_many({
        group_name: _make_marker_value()
        for group_name in group_names
    })


def _make_marker_value():
    """The value will be stored under the group_name key, and under any key belonging to that group."""
    return uuid.uuid4().hex


def _inc_call_count(func):
    if not hasattr(func, 'call_count'):
        setattr(func, 'call_count', 1)
    else:
        func.call_count += 1

