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

import logging

import git_annex_adapter.repo as repo
import git_annex_adapter.process as process
import git_annex_adapter.exceptions as exceptions

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def init_annex(
        path,
        description=None,
        version=None,
        ):
    """
    Initializes git-annex on the repository in the given *path*.

    Raises git_annex_adapter.exceptions.NotAGitRepoError if
    the given path is not already a git repository.

    Raises ValueError if given repository version is invalid.

    See git-annex-init documentation for more details.
    """
    runner = process.GitAnnexInitRunner(path)
    runner(description=description, version=version)
    return repo.GitAnnexRepo(path)


# Check git-annex version dependency
version_str = process.GitAnnexVersionRunner(None)(raw=True).stdout
logger.debug('git-annex version: {}'.format(version_str))

# git-annex uses '-gREF', NeuroDebian uses '+gitREF' as suffix
version_str = version_str.split('-g', 1)[0]
version_str = version_str.split('+git', 1)[0]

try:
    git_annex_version = float(version_str)
except ValueError:
    fmt = "Format of git-annex version {} not recognized."
    msg = fmt.format(git_annnex_version)
    raise ImportError(msg)

if git_annex_version < 6.20170101:
    fmt = "git-annex version {} must be at least {}"
    msg = fmt.format(git_annex_version, 6.20170101)
    raise ImportError(msg)

# Delete unnecessary variables
del version_str

