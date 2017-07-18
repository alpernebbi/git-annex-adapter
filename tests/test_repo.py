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
import pygit2

from tests.utils import ThreeAnnexedFilesTestCase

class TestGitAnnexRepoOnThreeFiles(ThreeAnnexedFilesTestCase):
    """Test adapter functions on a repo with flat file hierarchy."""

    def test_annex_keys(self):
        """Iterating GitAnnexRepo should give correct keys."""
        self.assertEqual(
            set(self.repo.annex),
            set(self.keys.values()),
        )

    def test_file_tree(self):
        """Flat AnnexedFileTree should be correct."""
        tree = self.repo.annex.get_file_tree()
        self.assertEqual(set(tree), set(self.files))

        for f, k in self.keys.items():
            with self.subTest(file=f):
                self.assertEqual(tree[f].key, k)


if __name__ == '__main__':
    unittest.main()

