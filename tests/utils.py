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
import sys
import unittest
import tempfile
import pathlib

import pygit2
import git_annex_adapter


class LoggedTestCase(unittest.TestCase):
    """Extends unittest.TestCase to print log messages to stderr."""
    def setUp(self):
        super().setUp()
        logging.basicConfig(
            format='[{levelname}] [{name}] {message}',
            style='{',
            level=logging.NOTSET,
            stream=sys.stderr,
        )


class TempDirTestCase(LoggedTestCase):
    """
    Extends unittest.TestCase to provide a temporary directory.

    The path to the temporary directory is assigned to the *tempdir*
    property of the instance during test setup.

    """
    def setUp(self):
        super().setUp()
        self._tempdir = tempfile.TemporaryDirectory(
            prefix='git-annex-adapter-tests-',
        )
        self._tempdir.__enter__()
        self.tempdir = pathlib.Path(self._tempdir.name)

    def tearDown(self):
        self._tempdir.__exit__(None, None, None)
        super().tearDown()


class TempRepoTestCase(TempDirTestCase):
    """
    Extends unittest.TestCase to provide a temporary git repo.

    The pygit2.Repository object representing the temporary git
    repo is assigned to the *repo* property of the instance
    during test setup.

    """
    def setUp(self):
        super().setUp()
        self.repo = pygit2.init_repository(str(self.tempdir))

    def git_commit(self):
        """Commit the current index to the git repository."""
        author = pygit2.Signature(
            'Git-Annex-Adapter Tester',
            'git-annex-adapter-tester@example.com',
            1500000000, # Date: 2017-07-14 02:40:00
        )

        try:
            parents = [self.repo.head.get_object().hex]
        except pygit2.GitError:
            parents = []

        return self.repo.create_commit(
            'HEAD', author, author, 'Test commit',
            self.repo.index.write_tree(), parents,
        )


class TempAnnexTestCase(TempRepoTestCase):
    """
    Extends unittest.TestCase to provide a temporary git-annex repo.

    The git_annex_adapter.repo.GitAnnexRepo object representing the
    temporary git-annex repo is assigned to the *repo* property of
    the instance during test setup.

    """
    def setUp(self):
        super().setUp()
        self.repo = git_annex_adapter.init_annex(self.repo.workdir)

    def tearDown(self):
        # Have to uninit before cleaning directory, since git-annex
        # marks its objects read-only so that they don't get deleted.
        subprocess.run(
            ['git', 'annex', 'uninit'],
            cwd=self.repo.workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        super().tearDown()

    def create_annexed_file(self, relpath, text):
        path = self.tempdir / relpath
        path.parents[0].mkdir(parents=True, exist_ok=True)
        path.write_text(text)

        subprocess.run(
            ['git', 'annex', 'add', '--quiet', relpath],
            cwd=self.repo.workdir,
            check=True,
        )


class ThreeAnnexedFilesTestCase(TempAnnexTestCase):
    """
    Extends unittest.TestCase to provide three annexed files in a
    git-annex repository.

    The files are "foo", "bar" and "baz"; and each file has its name
    as its content (without an terminating newline).

    """
    def setUp(self):
        super().setUp()

        self.files = ['foo', 'bar', 'baz']
        for f in self.files:
            self.create_annexed_file(f, f)

        # Actual keys for files
        self.keys = {
            'foo': 'SHA256E-s3--'
                '2c26b46b68ffc68ff99b453c1d304134'
                '13422d706483bfa0f98a5e886266e7ae',
            'bar': 'SHA256E-s3--'
                'fcde2b2edba56bf408601fb721fe9b5c'
                '338d10ee429ea04fae5511b68fbf8fb9',
            'baz': 'SHA256E-s3--'
                'baa5a0964d3320fbc0c6a922140453c8'
                '513ea24ab8fd0577034804a967248096',
        }

        self.git_commit()

