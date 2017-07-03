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
import git_annex_adapter

from tests.utils import TempDirTestCase
from tests.utils import TempRepoTestCase


class TestInitAnnexOnEmptyDir(TempDirTestCase):
    """Test init_annex on an empty temporary directory"""

    def test_init_annex_raises(self):
        """
        git-annex init fails if git isn't already initialized,
        so init_annex should raise an exception.
        """
        with self.assertRaises(Exception):
            git_annex_adapter.init_annex(self.tempdir)


class TestInitAnnexOnEmptyRepo(TempRepoTestCase):
    """Test init_annex on an empty temporary git repository"""

    def test_init_annex_success(self):
        """
        init_annex should work on a newly initialized git repo
        and return a GitAnnexRepo object. The repository should have
        a git-annex branch as a result.
        """
        annex_repo = git_annex_adapter.init_annex(self.repo.workdir)
        self.assertIsInstance(
            annex_repo,
            git_annex_adapter.repo.GitAnnexRepo,
        )
        self.assertIn('git-annex', annex_repo.listall_branches())


if __name__ == '__main__':
    unittest.main()

