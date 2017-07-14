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

import collections.abc
import logging
import pygit2

from .exceptions import NotAGitRepoError
from .exceptions import NotAGitAnnexRepoError

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

    def __getitem__(self, key):
        return AnnexedFile(key)

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


class AnnexedFile:
    """
    Represents a file stored by git-annex.

    """
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.key,
        )

