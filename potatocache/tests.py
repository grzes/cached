"""
PotatoCache
===========

What is it?
-----------

This is a helper app designed to help with expiring related caches. It provides a caching decorator `cached`
an `expire_key` and `expire_group` functions for expiring one or several cached values at once.

Let's go through an example. In a blogging app you might want to cache some author details, like this:

    >>> @cached(key='author1', groups=['author'], debug=True)
    ... def author_details(author):
    ...     '''doctest'''
    ...     return {'name': author.name}

    >>> author_details.__name__, author_details.__doc__
    ('author_details', 'doctest')

It's fairly obvious how it will work. The debug=True, results in annotating the function with the number of calls:
    >>> john = Author(name='John')
    >>> author_details(john)
    {'name': 'John'}
    >>> author_details.call_count
    1

After that it's still 1, because the subsequent results are fetched from cache without invoking the function:
    >>> author_details(john), author_details(john)
    ({'name': 'John'}, {'name': 'John'})
    >>> author_details.call_count
    1

"""
from potatocache import cached
from collections import namedtuple
Author = namedtuple('Author', 'name')
Post = namedtuple('Post', 'author text')
