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


We can set up an additional cached function, with a different key, but sharing a group. This time we'll use the arg_key
argument, which allows formating the cache key using the function's arguments:

    >>> @cached(arg_key='comment:%s', groups=['author1_data'], debug=True)
    ... def comment_details(comment_id):
    ...     comment = _comments[comment_id]  # it's like a database call!
    ...     return (comment.text, comment.author.name)

    >>> bob = Author(name='Bob')
    >>> _comments = {1: Comment(id=1, text='text1', author=john), 2: Comment(id=2, text='text2', author=bob)}
    >>> comment_details(1), comment_details(2)
    (('text1', 'John'), ('text2', 'Bob'))
    >>> comment_details.call_count
    2

Now if we alter the user's data we can expire the `author1_data` group with a single call, which will invalidate
the cache for both comment_details and author_details:

    >>> expire_group('author1_data')
    >>> (comment_details(1), author_details(john)) and comment_details.call_count, author_details.call_count
    3, 2


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

You probably noticed the post_details function above is broken, it's using the 'author1_data' group regardless of who
the post's author is. Let's rewrite it using an inner cached function:
This example is a bit of a stretch, because it assumes you already know the user_id, but it's just an example, ok?
#TODO: we need better examples.

    >>> def cached_comment(comment_id, author_id):
    ... @cached(key='comment:%s' % post_id, groups=['author%s_data' % author_id])
    ... def _cached_comment(comment_id, author_id):
    ...     comment = _comments[comment_id]  # it's like a database call!
    ...     return (comment.text, comment.author.name)
    ... return _cached_comment(comment_id, author_id)

Fetch everything again so it's recached. We can then expire the author1_data and see that keys in that group will hit the

    >>> cached_comment(1, 1), cached_comment(2, 2), author_details(john), author_details(bob)  # doctest:+ELLIPSIS
    ...

Now since the inner function is redefined on every call we can't rely on call_counts and will instead examine the data
to verify that group expiration correctly separates the values. First we update our data:
    >>> bob.name += '2'
    >>> john.name += '2'

Every cached function returns the old data:

    >>> cached_comment(1, 1), author_details(john), cached_comment(2, 2), author_details(bob)
    ('text1', 'John'), {'name': 'John'}, ('text2', 'Bob'), {'name': 'Bob'}

After expiring the author1_data group, keys belonging to that group will be reevaluated:

    >>> expire_group('author1_data')
    >>> cached_comment(1, 1), author_details(john), cached_comment(2, 2), author_details(bob)
    ('text1', 'John2'), {'name': 'John2'}, ('text2', 'Bob'), {'name': 'Bob'}


"""
from potatocache import cached, expire_group
from collections import namedtuple
Author = namedtuple('Author', 'name')
Comment = namedtuple('Comment', 'id author text')
