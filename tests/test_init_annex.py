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
from git_annex_adapter.exceptions import NotAGitRepoError

from tests.utils import TempDirTestCase
from tests.utils import TempRepoTestCase
from tests.utils import TempAnnexTestCase


class TestInitAnnexOnEmptyDir(TempDirTestCase):
    """Test init_annex on an empty temporary directory."""

    def test_init_annex_raises(self):
        """init_annex shouldn't work on empty directories."""
        with self.assertRaises(NotAGitRepoError):
            init_annex(str(self.tempdir))

    def test_init_annex_nonexistent(self):
        """init_annex shouldn't work on nonexistent directories."""
        with self.assertRaises(NotAGitRepoError):
            init_annex(str(self.tempdir / 'nonexistent'))


class TestInitAnnexOnEmptyRepo(TempRepoTestCase):
    """Test init_annex with wrong --version arguments."""

    def test_init_annex_version_negative(self):
        """Negative numbers shouldn't be valid versions."""
        with self.assertRaises(ValueError):
            init_annex(str(self.tempdir), version=-1)

    def test_init_annex_version_string(self):
        """Strings shouldn't be valid versions."""
        with self.assertRaises(ValueError):
            init_annex(str(self.tempdir), version='foo')

    def test_init_annex_version_five(self):
        """Repository version 5 should be valid."""
        annex_repo = init_annex(str(self.tempdir), version=5)
        self.assertGreaterEqual(annex_repo.config['annex.version'], '5')

    def test_init_annex_version_six(self):
        """Repository version 6 should be valid."""
        annex_repo = init_annex(str(self.tempdir), version=6)
        self.assertGreaterEqual(annex_repo.config['annex.version'], '6')

    def test_init_annex_description(self):
        """init_annex with description should update uuid.log."""
        repo = init_annex(str(self.tempdir), description='foo')
        uuid = repo.config['annex.uuid']
        uuid_log_blob = repo.revparse_single('git-annex:uuid.log')
        self.assertIn(
            "{} {} timestamp=".format(uuid, 'foo'),
            str(uuid_log_blob.data),
        )

    def test_init_annex_success(self):
        """init_annex should work on a new git repo."""
        annex_repo = init_annex(self.repo.workdir)
        self.assertIsInstance(annex_repo, GitAnnexRepo)
        self.assertIn('git-annex', annex_repo.listall_branches())


class TestInitAnnexOnEmptyAnnex(TempAnnexTestCase):
    """Test init_annex on an empty temporary git-annex repo."""

    def test_init_annex_success(self):
        """init_annex should work on an initialized git-annex repo."""
        self.repo = init_annex(self.repo.workdir)


if __name__ == '__main__':
    unittest.main()

