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

logger = logging.getLogger(__name__)


def init_annex(
        path,
        description=None,
        version=None,
        ):
    """
    Initializes git-annex on the repository in the given *path*.

    See git-annex-init documentation for more details.
    """
    cmd_line = ['git', 'annex', 'init']
    if description:
        cmd_line.append(description)
    if version:
        cmd_line.append('--version={}'.format(version))

    cmd_result = subprocess.run(
        cmd_line,
        cwd=path,
    )

    if not cmd_result.returncode:
        return GitAnnexRepo(path)

