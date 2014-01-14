"""
PotatoCache
===========

What is it?
-----------

This is a helper app designed to help with expiring related caches. It provides a caching decorator `cached`
an `expire_key` and `expire_group` functions for expiring one or several cached values at once.

For example in a blogging app you could cache Author's data and Comment text (which includes the Author's name).
When you update the Author you should invalidate both the Authors cache and each Comment's one, you can do that
in a single call to memcache if all your cached values were sharing a group name.


How it works?
-------------

The technique is apparently called 'memcache-tagging'. The basic idea is to tag a memcached key/value with a tag, allowing
expiration of several keys tagged with the same tag. One approach is to simply incorporate the tag value in the key.
First you ask memcache for the current tag value and then, instead of asking for '<key>', you ask for '<tag_value>-<key>'.
Another approach is to store the tag value alongside the cached value, fetch them both at once with `memcache.get_multi`
and check if the tag value matches.


Group keys - A simple detailed example!
---------------------------------------

Let's go through a detailed example. In a blogging app you might want to cache some author details, like this:

    >>> @cached(key='author1', groups=['author1_data'], debug=True)
    ... def author_details(author):
    ...     '''doctest'''
    ...     return {'name': author.name}

    >>> author_details.__name__, author_details.__doc__
    ('author_details', 'doctest')

It's fairly obvious how it will work. The debug=True, results in annotating the function with the number of calls:
    >>> john = Author(1, name='John')
    >>> author_details(john)
    {'name': 'John'}
    >>> author_details.call_count
    1

After that it's still 1, because the subsequent results are fetched from cache without invoking the function:
    >>> author_details(john), author_details(john)
    ({'name': 'John'}, {'name': 'John'})
    >>> author_details.call_count
    1


We can set up an additional cached function, with a different key, but sharing a group. This time we'll use the arg_key
argument, which allows formating the cache key using the function's arguments:

    >>> @cached(arg_key='comment:%s', groups=['author1_data'], debug=True)
    ... def comment_details(comment_id):
    ...     comment = _comments[comment_id]  # it's like a database call!
    ...     return (comment.text, comment.author.name)

    >>> bob = Author(2, name='Bob')
    >>> _comments = {1: Comment(id=1, text='text1', author=john), 2: Comment(id=2, text='text2', author=bob)}
    >>> comment_details(1), comment_details(2)
    (('text1', 'John'), ('text2', 'Bob'))
    >>> comment_details.call_count
    2

Now if we alter the user's data we can expire the `author1_data` group with a single call, which will invalidate
the cache for both comment_details and author_details:

    >>> expire_group('author1_data')
    >>> (comment_details(1), author_details(john)) and comment_details.call_count, author_details.call_count
    (3, 2)


Fixed `key` vs `arg_key`
------------------------

While it's convenient to have the key computed based on the argument, it's often more flexible to have an explicit
inner function - cached with a fixed key. That function can take additional arguments, used for evaluation, but not
for key generation:

    def cached_post(post, last_comment):
        @cached(key='post:%s' % post.id)
        def _cached_post(post, last_comment):
            return {
                'text': post.text,
                'last_comment_date': last_comment.date
            }
        return _cached_post(post, last_comment)

You probably noticed the comment_details and author_details functions above are broken, they're using the 'author1_data'
group regardless of who the comment's author is. Let's rewrite them using an inner cached function:
(This example is a bit of a stretch, because it assumes you already know the user_id, but it's just an example, ok?)
#TODO: we need better examples.

    >>> def cached_comment(comment_id, author_id):
    ...     @cached(key='comment:%s' % comment_id, groups=['author%s_data' % author_id])
    ...     def _cached_comment(comment_id, author_id):
    ...         comment = _comments[comment_id]  # it's like a database call!
    ...         return (comment.text, comment.author.name)
    ...     return _cached_comment(comment_id, author_id)

    >>> def author_details(author):
    ...     @cached(key='author:%s' % author.id, groups=['author%s_data' % author.id])
    ...     def _author_details(author):
    ...        return {'name': author.name}
    ...     return _author_details(author)

Fetch everything again so it's recached. We can then expire the author1_data and see that keys in that group will return
fresh data, while keys in author2_data - won't.

    >>> cached_comment(1, 1), cached_comment(2, 2), author_details(john), author_details(bob)  # doctest:+ELLIPSIS
    (...

Now since the inner function is redefined on every call we can't rely on call_counts and will instead examine the data
to verify that group expiration correctly separates the values. First we update our data:
    >>> bob.name += '2'
    >>> john.name += '2'

Every cached function returns the old data:

    >>> cached_comment(1, 1), author_details(john), cached_comment(2, 2), author_details(bob)
    (('text1', 'John'), {'name': 'John'}, ('text2', 'Bob'), {'name': 'Bob'})

After expiring the author1_data group, keys belonging to that group will be reevaluated:

    >>> expire_group('author1_data')
    >>> cached_comment(1, 1), author_details(john), cached_comment(2, 2), author_details(bob)
    (('text1', 'John2'), {'name': 'John2'}, ('text2', 'Bob'), {'name': 'Bob'})


We can have a key belonging to many groups, and as soon as anyone of them is invlidated, the key's cached value becomes stale.


Existing solutions
------------------

This comparison (https://www.djangopackages.com/grids/g/caching/) evaluates different caching utilities. It singles
out two packages that support memcache-tagging:


https://bitbucket.org/evotech/cache-tagging

This one is really close to this implementation, has the advantage of matching the Django cache backend api. This
api compatibility comes with a cost: First; It takes two separate cache queries for the main value and tag values.
Second; Since the api provides separate set/get functions it stores new tag values (invalidates them) based on
what was previously fetched in threadlocals (instead of leaving current values fetched from cache).

It does however have funky transaction support, and updated template caching tags.

https://bitbucket.org/kmike/django-cache-utils

This has the same problems: Makes several trips to memcache. Additionally it takes a weird approach to building cache keys
for instance methods, it ignores the instance. It's invalidate method looks broken (cached by `func_type()`, but
invalidates explicitly by 'function')

It looks like a good candidate to fork and fix, but again it's compatibility with the backend api makes what
we're trying to do here a little akward.

It does have a nice CACHE_MINT feature, keeping stale objects in cache while they're regenerated - but the whole point
of exact invalidation is to allow the values to get naturally evicted from memcache, or explicitly invalidated.

The author started working on a simplified version, which addresses some of these issues, but drops the taging support
completely.

Both aren't actively maintained, although the second looks slightly more lively



"""
import unittest, doctest
from potatocache import cached, expire_group
from django.test import TestCase

class Author(object):
    def __init__(self, id, name):
        self.id, self.name = id, name

class Comment(object):
    def __init__(self, id, text, author):
        self.id, self.text, self.author = id, text, author


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite('potatocache.tests'))
    return tests


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite('potatocache.tests'))
    return suite

