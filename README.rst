=================
Git-Annex-Adapter
=================
This package lets you call git-annex_ commands from within Python.
Commands are executed using ``subprocess`` and use their batch versions whenever possible.

.. _git-annex: https://git-annex.branchable.com/

Requirements
------------
- Python 3
- git-annex 6.20160726 (or later)

The git-annex version in your distro's repositories might not satisfy this. In that case, you might want to look at
the ``git-annex-standalone`` package in the NeuroDebian_ repository.

.. _NeuroDebian: http://neuro.debian.net/

Usage
-----
Create and wrap a repo::

    >>> from git_annex_adapter import GitAnnex
    >>> annex = GitAnnex('/path/to/repo', create=True)

Import a folder or a file into the annex::

    >>> annex.calckey('/path/to/file.txt')
    'SHA256E-s17--2b9a58f3fe5d2eee4d7276831c1c9f7811b697ae4904f9db9090dda71cfcbe80.txt'
    >>> annex.import_('/path/to/file.txt')

Get the backend key for the file in the annex::

    >>> key = annex.lookupkey('file.txt')
    >>> key
    'SHA256E-s17--2b9a58f3fe5d2eee4d7276831c1c9f7811b697ae4904f9db9090dda71cfcbe80.txt'

Get the actual location of the file::

    >>> annex.locate(key, absolute=True)
    '/path/to/repo/.git/annex/objects/ZP/mq/.../...' # Not literal ellipses

Get annexed keys or files::

    >>> annex.keys()
    {'SHA256E-s17--2b9a58f3fe5d2eee4d7276831c1c9f7811b697ae4904f9db9090dda71cfcbe80.txt'}
    >>> annex.files()
    {'file.txt'}

Access the git-annex metadata belonging to the file::

    >>> file_metadata = annex['file.txt']
    >>> # file_metadata = annex[key] works as well
    >>> list(file_metadata.keys())
    ['month', 'tag', 'year']

    >>> len(file_metadata)
    3

    >>> file_metadata['tag']
    ['temporary', 'test']

    >>> file_metadata['non-existent-field']
    []

    >>> file_metadata['lastchanged']
    ['2016-11-25@10-56-48']

Manipulate the metadata::

    >>> file_metadata['tag'].append('new')
    >>> file_metadata['tag']
    ['temporary', 'test', 'more']

    >>> del file_metadata['tag']
    >>> file_metadata['tag']
    []
    >>> list(file_metadata.keys())
    ['month', 'year']

    >>> file_metadata['tag'] = ['alpha', 'beta']
    >>> print(*file_metadata.items())
    ('month', ['11']) ('tag', ['alpha', 'beta']) ('year', ['2016'])

Notes
-----
- Since the initial focus was on metadata functionality of git-annex, many other commands are not yet implemented.
- The ``key`` and ``file`` metadata fields are used internally, so they don't represent actual metadata.
- Metadata that ends with ``lastchanged`` are git-annex internal timestamps. They are ignored when iterating fields.
- ``metadata()``, ``keys()``, ``files()``, ``fields()`` functions are cached assuming there won't be external changes.
  If a new file/key is added/removed from the annex, it won't be available until either ``clear_metadata_cache()``
  is called or one of the functions is called with ``cached=False``.
- Metadata objects also use caching, but their cache is updated everytime any field is set or deleted.
  If any field is externally modified during operation, this might cause overwriting the field due to an oversight.
  Git-annex ignores setting the ``lastchanged`` field, but trying to do so would update the cache without any loss.
