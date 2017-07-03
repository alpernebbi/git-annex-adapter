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

    try:
        cmd_result = subprocess.run(
            cmd_line,
            cwd=path,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            check=True,
            universal_newlines=True,
        )
    
    except OSError as err:
        logger.exception('init_annex failed: {}'.format(err.strerror))
        logger.debug('init_annex args: {}'.format({
            'path':path,
            'version':version,
            'description':description
        }))
        raise

    except subprocess.CalledProcessError as err:
        logger.exception('init_annex failed: {}'.format(err.stderr))
        logger.debug('init_annex args: {}'.format({
            'path': path,
            'version': version,
            'description': description
        }))
        raise

    else:
        return GitAnnexRepo(path)

