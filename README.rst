=================
Git-Annex-Adapter
=================
This package lets you interact with git-annex_ from within Python.
Necessary commands are executed using ``subprocess`` and use their
batch versions whenever possible.

.. _git-annex: https://git-annex.branchable.com/

I'm developing this as needed, so feel free to ask if there's any
functionality you want me to implement.

Requirements
------------
- Python 3
- git-annex 6.20170101 (or later)
- pygit2 0.24 (or later)

Usage
-----
To create a git-annex repository from scratch::

    >>> from pygit2 import init_repository
    >>> from git_annex_adapter import init_annex

    >>> init_repository('/path/to/repo')
    pygit2.Repository('/path/to/repo/.git/')

    >>> init_annex('/path/to/repo')
    git_annex_adapter.repo.GitAnnexRepo(/path/to/repo/.git/)

To wrap an existing git-annex repository::

    >>> from git_annex_adapter.repo import GitAnnexRepo
    >>> repo = GitAnnexRepo('/tmp/repo')

The GitAnnexRepo is a subclass of pygit2.Repository. Git-annex specific
functionality is accessed via the ``annex`` property of it, which is
a mapping object from git-annex keys to ``AnnexedFile`` objects::

    >>> for key in repo.annex:
    ...     print(key)
    SHA256E-s3--2c26...
    SHA256E-s3--baa5...
    SHA256E-s3--fcde...

    >>> key = 'SHA256E-s3--2c26...'
    >>> repo.annex[key]
    git_annex_adapter.repo.AnnexedFile('SHA256E-s3--2c26...')

You can also get a tree representation of any git tree-ish object with
annexed file entries replaced with ``AnnexedFile`` objects::

    >>> tree = repo.annex.get_file_tree() # treeish='HEAD'
    >>> tree
    git_annex_adapter.repo.AnnexedFileTree(4d7f...)

    >>> set(tree)
    {'foo', 'bar', 'baz', 'README', 'directory'}

    >>> tree['foo']
    git_annex_adapter.repo.AnnexedFile(SHA256E-s3--2c26...)

    >>> tree['directory']
    git_annex_adapter.repo.AnnexedFileTree(8b54...)

    >>> tree['directory/file'] # or tree['directory']['file']
    <pygit2.Blob object at 0x...>

The ``AnnexedFile`` objects can be used to access and manipulate
information about a file.

The ``metadata`` property of the ``AnnexedFile`` is a mutable mapping
object from fields to sets of values::

    >>> foo = tree['foo']
    >>> for field, values in foo.metadata:
    ...     print('{}: {}'.format(field, values))
    author: {'me'}
    numbers: {'1', '2', '3'}

    >>> foo.metadata['numbers'] |= {'0'}
    >>> foo.metadata['numbers'] -= {'3'}
    >>> foo.metadata['numbers']
    {'0', '2'}

    >>> del foo.metadata['author']
    >>> 'author' in foo.metadata
    False

    >>> foo.metadata['lastchanged']
    '2017-07-19@15-00-00'

Calling Processes
-----------------

If you need low-level access to the git-annex processes, you can do it
via the classes included in ``process`` module::

    >>> from git_annex_adapter.process import ...

Subclasses of ``GitAnnexBatchProcess`` return relevant output (usually
one line or a dict object) whenever called with a line of input.
For example, ``git-annex metadata --batch --json``::

    >>> proc = GitAnnexMetadataBatchJsonProcess('/path/to/repo')
    >>> proc(file='foo')
    {..., 'key':'SHA256E-s3--2c26...', 'fields': ...}

    >>> proc(file='foo', fields={'numbers': ['1', '2', '3']})
    {..., 'key': ..., 'fields': {'numbers': ['1', '2', '3'], ...}}

Subclasses of ``GitAnnexRunner`` call a single program with
different arguments. They return a ``subprocess.CompletedProcess``
when called, which captures stdout and stderr. For example, to run
``git-annex version``::

    >>> runner = GitAnnexVersionRunner('/path/to/repo')
    >>> runner(raw=True)
    CompletedProcess(..., stdout='6.20170101', stderr='')

    >>> print(runner().stdout)
    git-annex version: 6.20170101
    ...

