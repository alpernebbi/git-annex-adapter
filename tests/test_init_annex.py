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

from git_annex_adapter import init_annex
from git_annex_adapter.repo import GitAnnexRepo

from tests.utils import TempDirTestCase
from tests.utils import TempRepoTestCase
from tests.utils import TempAnnexTestCase


class TestInitAnnexOnEmptyDir(TempDirTestCase):
    """Test init_annex on an empty temporary directory"""

    def test_init_annex_raises(self):
        """
        git-annex init fails if git isn't already initialized,
        so init_annex should raise an exception.
        """
        with self.assertRaises(Exception):
            init_annex(self.tempdir)


class TestInitAnnexOnEmptyRepo(TempRepoTestCase):
    """Test init_annex on an empty temporary git repository"""

    def test_init_annex_success(self):
        """
        init_annex should work on a newly initialized git repo
        and return a GitAnnexRepo object. The repository should have
        a git-annex branch as a result.
        """
        annex_repo = init_annex(self.repo.workdir)
        self.assertIsInstance(annex_repo, GitAnnexRepo)
        self.assertIn('git-annex', annex_repo.listall_branches())


class TestInitAnnexOnEmptyAnnexRepo(TempAnnexTestCase):
    """Test init_annex on an empty temporary git-annex repo"""

    def test_init_annex_success(self):
        """
        Running init_annex on an already initialized git-annex
        repository should succeed.
        """
        self.repo = init_annex(self.repo.workdir)


if __name__ == '__main__':
    unittest.main()

