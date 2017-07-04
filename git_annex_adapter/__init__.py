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

import subprocess
import logging

from .repo import GitAnnexRepo
from .exceptions import NotAGitRepoError
from .process import ProcessRunner

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
    runner = ProcessRunner('git-annex', 'init', workdir=path)

    args = []
    if description is not None:
        args.append(description)
    if version is not None:
        args.append('--version={}'.format(version))

    try:
        cmd_result = runner(*args)

    except FileNotFoundError as err:
        if "No such file or directory:" in err.strerror:
            msg = "Path '{}' does not exist."
            raise NotAGitRepoError(msg) from err
        else:
            logger.debug("init_annex path: {}".format(path))
            logger.debug("init_annex args: {}".format(args))
            logger.debug("init_annex error: {}".format(err.strerror))
            raise

    except subprocess.CalledProcessError as err:
        if "git-annex: Not in a git repository" in err.stderr:
            msg = "Path '{}' is not in a git repository."
            raise NotAGitRepoError(msg) from err

        elif "option --version:" in err.stderr:
            msg = "Repository version '{}' is invalid."
            raise ValueError(msg) from err

        else:
            logger.debug("init_annex path: {}".format(path))
            logger.debug("init_annex args: {}".format(args))
            logger.debug("init_annex stderr: \n{}".format(err.stderr))
            raise

    else:
        return GitAnnexRepo(path)

