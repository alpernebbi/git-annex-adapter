# Git-Annex-Adapter
# Copyright (C) 2017 Alper Nebi Yasak
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import types
import collections.abc
import logging
import pygit2

from .exceptions import NotAGitRepoError
from .exceptions import NotAGitAnnexRepoError
from .process import GitAnnexMetadataBatchJsonProcess
from .process import GitAnnexContentlocationBatchProcess

logger = logging.getLogger(__name__)


class GitAnnexRepo(pygit2.Repository):
    """
    Provides git and git-annex functionality.

    This class extends pygit2.Repository by only adding an *annex*
    property that can be used to access git-annex functionality.
    Constructor arguments are the same as that of pygit2.Repository.

    See pygit2.Repository and git_annex_adapter.GitAnnex for git or
    git-annex specific documentation.

    """
    def __init__(self, path, *args, **kwargs):
        try:
            super().__init__(path, *args, **kwargs)

        except KeyError as err:
            if err.args == (path,):
                fmt = "Path {} is not a valid git repository"
                msg = fmt.format(path)
                raise NotAGitRepoError(msg) from err
            else:
                raise

        self.annex = GitAnnex(self)

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.path,
        )


class GitAnnex(collections.abc.Mapping):
    """
    Provides git-annex functionality.

    """
    def __init__(self, repo):
        # Must have run git-annex init
        if repo.lookup_branch('git-annex') is None:
            fmt = 'Repository {} is not a git-annex repo.'
            msg = fmt.format(repo)
            raise NotAGitAnnexRepoError(msg)

        self.repo = repo

        self.processes = types.SimpleNamespace()
        self.processes.metadata = \
            GitAnnexMetadataBatchJsonProcess(self.repo.workdir)
        self.processes.contentlocation = \
            GitAnnexContentlocationBatchProcess(self.repo.workdir)

    def get_file_tree(self, treeish='HEAD'):
        """Returns an AnnexedFileTree for the given treeish"""
        return AnnexedFileTree(self.repo, treeish=treeish)

    def __getitem__(self, key):
        return AnnexedFile(self.repo, key)

    def __iter__(self):
        root = self.repo.revparse_single('git-annex^{tree}')
        # git-annex:aaa/bbb/*.log
        yield from (
            logf.name[:-4]
            for aaa in root
            if aaa.type == 'tree'
            for bbb in self.repo[aaa.id]
            if bbb.type == 'tree'
            for logf in self.repo[bbb.id]
            if logf.type == 'blob' \
            and logf.name.endswith('.log')
        )

    def __len__(self):
        return sum(1 for _ in iter(self))

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.repo.path,
        )

class AnnexedFileTree(collections.abc.Mapping):
    """
    Represents a hierarchy of files in a git-annex repository.

    Takes a treeish git revision, translates the resulting pygit2.Tree
    object into an easily interactable mapping. Any pygit2.TreeEntry
    objects representing annexed files and git objects are replaced
    with AnnexedFile, AnnexedFileTree and pygit2.Blob objects.

    """
    def __init__(self, repo, treeish='HEAD'):
        super().__init__()
        self.repo = repo
        self._rev = repo.revparse_single(treeish)
        self._tree = self._rev.peel(pygit2.Tree)

    def __iter__(self):
        for entry in self._tree:
            yield entry.name

    def __getitem__(self, path):
        entry = self._tree[path]
        obj = self.repo[entry.hex]

        if entry.type == 'tree':
            return AnnexedFileTree(self.repo, treeish=entry.hex)

        elif entry.type == 'blob' and not obj.is_binary:
            try:
                blob = obj.data.decode()
            except UnicodeDecodeError:
                fmt = "Nonbinary blob '{}' ({}) failed to decode."
                msg = fmt.format(entry.name, entry.hex)
                logger.debug(msg)
                blob = ''

            # ../../../.git/annex/objects/aa/bb/*/*
            if blob.strip('./').startswith('git/annex/objects/'):
                _, _, key = blob.rpartition('/')
                return self.repo.annex[key]

        return obj

    def __len__(self):
        return len(self._tree)

    def __str__(self):
        return super().__repr__()

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self._tree.id,
        )


class AnnexedFile:
    """
    Represents a file stored by git-annex.

    """
    def __init__(self, repo, key):
        self.repo = repo
        self.key = key
        self.metadata = AnnexedFileMetadata(self)
        self._contentlocation = None

    @property
    def contentlocation(self):
        """Returns the absolute filename to the content of this key."""
        if self._contentlocation:
            return self._contentlocation

        process = self.repo.annex.processes.contentlocation
        relpath = process(self.key)
        if not relpath:
            return None

        abspath = os.path.join(self.repo.workdir, relpath)
        self._contentlocation = abspath
        return self._contentlocation

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.key,
        )


class AnnexedFileMetadata(collections.abc.MutableMapping):
    """
    Represents the metadata for a file stored by git-annex.

    The output is cached, so if the metadata is externally modified,
    it might not be correct until a reassignment is made. If you
    assign to the externally modified field, that modification would
    be overridden by yours.

    The 'lastchanged' field and other fields ending with '-lastchanged'
    are not externally modifiable, so this class skips them while
    iterating metadata fields. However, they are still accessible.

    Since git-annex does not keep the order of values for a field,
    the values are returned as sets.

    """
    def __init__(self, file):
        self.file = file
        self._process = file.repo.annex.processes.metadata
        self._cache = None

    def _metadata(self, fields=None):
        """Get unprocessed, cached fields object for this file."""
        if fields:
            output = self._process(key=self.file.key, fields=fields)
            self._cache = output['fields']

        elif self._cache is None:
            output = self._process(key=self.file.key)
            self._cache = output['fields']

        return self._cache

    def __getitem__(self, field):
        """Get the value of a single field for this file."""
        return set(self._metadata()[field])

    def __setitem__(self, field, value):
        """Set the value of a single field for this file."""
        if not isinstance(value, set):
            fmt = "Field '{}' value '{}' must be a set."
            msg = fmt.format(field, value)
            raise TypeError(msg)
        self._metadata({field: list(value)})

    def __delitem__(self, field):
        """Remove given field from this file."""
        self._metadata({field: []})

    def __iter__(self):
        """Iterate noninternal fields for this file."""
        # Skip 'lastchanged' and fields that end in '-lastchanged'
        for f in self._metadata():
            if f != 'lastchanged' and not f.endswith('-lastchanged'):
                yield f

    def __len__(self):
        """Return number of noninternal fields."""
        return sum(1 for _ in iter(self))

    def update(self, *args, **kwargs):
        """Update fields for this file from a dict or keyword args."""
        if len(args) > 1:
            fmt = 'update expected at most 1 arguments, got {}.'
            msg = fmt.format(len(args))
            raise TypeError(msg)

        fields = args[0] if args else {}
        fields.update(kwargs)

        for field, value in fields.items():
            if not isinstance(value, set):
                fmt = "Field '{}' value '{}' must be a set."
                msg = fmt.format(field, value)
                raise TypeError(msg)
            fields[field] = list(value)

        self._metadata(fields)

    def clear(self):
        """Remove all fields for this file."""
        self._metadata({f: [] for f in self})

    def __str__(self):
        return str(dict(self))

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.file.key,
        )

