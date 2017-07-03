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

import unittest
import tempfile


class TempDirTestCase(unittest.TestCase):
    """
    Extends unittest.TestCase to provide a temporary directory.

    The path to the temporary directory is assigned to the *tempdir*
    property of the instance during test setup.

    """
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory(
            prefix='git-annex-adapter-tests-',
        )
        self._tempdir.__enter__()
        self.tempdir = self._tempdir.name

    def tearDown(self):
        self._tempdir.__exit__(None, None, None)

