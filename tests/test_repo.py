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
import pathlib
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

    def test_metadata_mapping(self):
        """AnnexedKeyMetadata should work as a mapping."""
        file = self.files[0]
        key = self.keys[file]
        metadata = self.repo.annex[key].metadata
        self.assertEqual(dict(metadata), {})

        metadata['file'] = {file}
        metadata['key'] = {key}
        self.assertEqual(set(metadata), {'file', 'key'})
        self.assertEqual(metadata['file'], {file})
        self.assertEqual(metadata['key'], {key})

        metadata.clear()
        self.assertEqual(dict(metadata), {})

        metadata.update(
            {'foo': {'bar'}},
            numbers={'1', '2', '3', '4'},
            author={'me'},
        )
        self.assertEqual(set(metadata), {'foo', 'numbers', 'author'})
        self.assertEqual(metadata['foo'], {'bar'})
        self.assertEqual(metadata['numbers'], {'1', '2', '3', '4'})
        self.assertEqual(metadata['author'], {'me'})

        del metadata['author']
        self.assertNotIn('author', metadata)

        metadata['numbers'] |= {'0'}
        metadata['numbers'] -= {'3', '4'}
        self.assertEqual(metadata['numbers'], {'0', '1', '2'})

        self.assertIn('lastchanged', metadata)
        self.assertNotIn('lastchanged', set(metadata))

        # In git-annex < 6.20161213 this triggers a bug
        metadata['bug'] = {'a'}
        metadata['bug'] = {'b'}
        metadata['bug'] = {'c'}
        metadata['bug'] = {'a'}
        self.assertEqual(metadata['bug'], {'a'})

    def test_contentlocation_is_correct(self):
        """Item contentlocations should be correct"""
        for file, key in self.keys.items():
            item = self.repo.annex[key]
            with self.subTest(file=file):
                p = pathlib.Path(item.contentlocation)
                self.assertTrue(p.is_absolute())
                self.assertTrue(p.is_file())
                self.assertTrue(p.exists())
                self.assertEqual(p.read_text(), file)

if __name__ == '__main__':
    unittest.main()

