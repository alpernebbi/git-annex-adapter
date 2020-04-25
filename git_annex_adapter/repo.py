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
from .process import GitAnnexFindJsonRunner

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

        self.runners = types.SimpleNamespace()
        self.runners.find = \
            GitAnnexFindJsonRunner(self.repo.workdir)

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
            if (aaa.type == 'tree' or aaa.type == pygit2.GIT_OBJ_TREE)
            for bbb in self.repo[aaa.id]
            if (bbb.type == 'tree' or bbb.type == pygit2.GIT_OBJ_TREE)
            for logf in self.repo[bbb.id]
            if (logf.type == 'blob' or logf.type == pygit2.GIT_OBJ_BLOB) \
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
        if isinstance(treeish, pygit2.Index):
            self._oid = treeish.write_tree(self.repo)
            self._tree = repo[self._oid]
        else:
            self._rev = repo.revparse_single(treeish)
            self._tree = self._rev.peel(pygit2.Tree)

    def __iter__(self):
        for entry in self._tree:
            yield entry.name

    def __getitem__(self, path):
        entry = self._tree[path]
        obj = self.repo[entry.hex]

        if entry.type == 'tree' or entry.type == pygit2.GIT_OBJ_TREE:
            return AnnexedFileTree(self.repo, treeish=entry.hex)

        elif (entry.type == 'blob' or entry.type == pygit2.GIT_OBJ_BLOB) \
                and not obj.is_binary:
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

    def find(self, *paths, match_opts=None):
        proc = self.repo.annex.runners.find(
            *paths, match_opts=match_opts, branch=self._tree.hex,
        )
        for obj in proc.stdout_objs:
            yield obj["file"]


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


class AnnexMatchingOptions(collections.UserList):
    """
    Represents matching options you can pass to some git-annex commands.

    You can either pass a list of options to the constructor of this
    class, or you can chain multiple calls on an empty instance to build
    up the command line arguments.

    For example, you can construct this option chain:

        --include=*.mp3 --and -( --in=usbdrive --or --in=archive -)

    By passing it literally to the constructor:

        match = AnnexMatchingOptions([
            "--include=*.mp3", "--and", "-(",
                "--in=usbdrive", "--or", "--in=archive",
            "-)",
        ])

    Or by using bitwise operations within Python:

        mp3s = AnnexMatchingOptions().include("*.mp3")
        in_usbdrive = AnnexMatchingOptions().in_("usbdrive")
        in_archive = AnnexMatchingOptions().in_("archive")
        match = mp3s & (in_usbdrive | in_archive)

    Or by mixing the two:

        match = AnnexMatchingOptions().include("*.mp3")
        match &= ["--in=usbdrive", "--or", "--in=archive"]

    The bitwise operators may automatically group their operands, so the
    final commandline string can slightly differ from the original,
    while still being semantically equal.

    Also see git-annex-matching-options(1) for the explanations for
    these options.

    """

    def include(self, glob):
        return self + ['--include={}'.format(glob)]

    def exclude(self, glob):
        return self + ['--exclude={}'.format(glob)]

    def in_(self, repo, date=None):
        opts = []
        if date is None:
            opts.append('--in={}'.format(repo))
        else:
            opts.append('--in={}@{}'.format(repo, date))
        return self + opts

    def copies(self, count, trustlevel=None, group=None):
        opts = []
        if trustlevel is not None:
            opts.append('--copies={}:{}'.format(trustlevel, count))
        if group is not None:
            opts.append('--copies={}:{}'.format(group, count))
        if opts == []:
            opts.append('--copies={}'.format(count))
        return self + opts

    def lackingcopies(self, count):
        return self + ['--lackingcopies={}'.format(count)]

    def approxlackingcopies(self, count):
        return self + ['--approxlackingcopies={}'.format(count)]

    def inbackend(self, backend):
        return self + ['--inbackend={}'.format(count)]

    @property
    def securehash(self):
        return self + ['--securehash']

    def inallgroup(self, group):
        return self + ['--inallgroup={}'.format(group)]

    def smallerthan(self, size):
        return self + ['--smallerthan={}'.format(size)]

    def largerthan(self, size):
        return self + ['--largerthan={}'.format(size)]

    def metadata(self, *conditions, **kwargs):
        opts = []
        for c in conditions:
            opts.extend(('--metadata', c))
        for key, value in kwargs.items():
            opts.extend(('--metadata', '{}={}'.format(key, value)))
        return self + opts

    @property
    def want_get(self):
        return self + ['--want-get']

    @property
    def want_drop(self):
        return self + ['--want-drop']

    def accessedwithin(self, interval):
        return self + ['--accessedwithin={}'.format(interval)]

    @property
    def unlocked(self):
        return self + ['--unlocked']

    @property
    def locked(self):
        return self + ['--locked']

    def mimetype(self, glob):
        return self + ['--mimetype={}'.format(glob)]

    def mimeencoding(self, glob):
        return self + ['--mimeencoding={}'.format(glob)]

    def __invert__(self):
        return AnnexMatchingOptions(
            ['--not', '-(', *self, '-)']
        )

    def __and__(self, other):
        return AnnexMatchingOptions(
            ['-(', *self, '-)', '--and', '-(', *other, '-)']
        )

    def __rand__(self, other):
        return AnnexMatchingOptions(
            ['-(', *other, '-)', '--and', '-(', *self, '-)']
        )

    def __iand__(self, other):
        self.data = ['-(', *self, '-)', '--and', '-(', *other, '-)']
        return self

    def __or__(self, other):
        return AnnexMatchingOptions(
            ['-(', *self, '-)', '--or', '-(', *other, '-)']
        )

    def __ror__(self, other):
        return AnnexMatchingOptions(
            ['-(', *other, '-)', '--or', '-(', *self, '-)']
        )

    def __ior__(self, other):
        self.data = ['-(', *self, '-)', '--or', '-(', *other, '-)']
        return self
