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
import subprocess

from .exceptions import NotAGitRepoError

logger = logging.getLogger(__name__)


class ProcessRunner:
    """
    Helper class to repeatedly run a program with different arguments

    git_proc = ProcessRunner(['git'], workdir='/path/to/repo')
    result = git_proc('status', '-sb')
    print(result.stdout)

    """
    def __init__(self, args_prefix, workdir):
        self.args_prefix = args_prefix
        self.workdir = workdir
        self.logger = logging.getLogger('{name}.{cls}'.format(
            name=__name__,
            cls=self.__class__.__name__,
        ))

    def __call__(self, *args_suffix):
        return subprocess.run(
            (*self.args_prefix, *args_suffix),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self.workdir,
            check=True,
        )

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args={
                "args_prefix": self.args_prefix,
                "workdir": self.workdir,
            }
        )


class GitAnnexRunner(ProcessRunner):
    """Helper class to run git-annex commands."""
    def __init__(self, args_prefix, workdir):
        args_prefix = ('git-annex', *args_prefix)
        super().__init__(args_prefix, workdir)

    def __call__(self, *args_suffix):
        try:
            return super().__call__(*args_suffix)

        except FileNotFoundError as err:
            if "No such file or directory:" in err.strerror:
                fmt = "Path '{}' does not exist."
                msg = fmt.format(self.workdir)
                raise NotAGitRepoError(msg) from err
            else:
                raise

        except subprocess.CalledProcessError as err:
            if "git-annex: Not in a git repository" in err.stderr:
                fmt = "Path '{}' is not in a git repository."
                msg = fmt.format(self.workdir)
                raise NotAGitRepoError(msg) from err
            else:
                raise


class GitAnnexInitRunner(GitAnnexRunner):
    """Helper class to run git-annex init commands."""
    def __init__(self, workdir):
        super().__init__(['init'], workdir)

    def __call__(self, description=None, version=None):
        args = []
        if description is not None:
            args.append(description)
        if version is not None:
            args.append('--version={}'.format(version))

        try:
            return super().__call__(*args)

        except subprocess.CalledProcessError as err:
            if "option --version:" in err.stderr:
                fmt = "Repository version '{}' is invalid."
                msg = fmt.format(version)
                raise ValueError(msg) from err
            else:
                self.logger.debug("Unknown error:\n", exc_info=True)
                self.logger.debug("stderr:\n{}".format(err.stderr))
                raise
 
        except:
            self.logger.debug("Unknown error:\n", exc_info=True)
            raise

