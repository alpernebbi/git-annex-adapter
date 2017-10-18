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

import pathlib
import subprocess
import unittest

from git_annex_adapter.process import LineReaderQueue
from git_annex_adapter.process import LineWriterQueue
from git_annex_adapter.process import Process
from git_annex_adapter.process import JsonProcess
from git_annex_adapter.process import ProcessRunner
from git_annex_adapter.process import GitAnnexBatchProcess
from git_annex_adapter.process import GitAnnexBatchJsonProcess

from tests.utils import TempDirTestCase
from tests.utils import TempRepoTestCase
from tests.utils import TempAnnexTestCase
from tests.utils import ThreeAnnexedFilesTestCase


class TestQueuesOnEmptyDir(TempDirTestCase):
    """Test line reader/writer queues on an empty directory"""

    def setUp(self):
        super().setUp()
        self.testfile = self.tempdir / 'test.txt'
        self.lines = ['{:^3}'.format(i) for i in range(1000)]

    def test_queue_writer_with_file(self):
        """LineWriterQueue written file should be correct"""

        with self.testfile.open('w') as f:
            q = LineWriterQueue(f)
            for line in self.lines:
                q.put(line)
            q.put(None)

        with self.testfile.open('r') as f:
            self.assertEqual(
                f.readlines(),
                [x + '\n' for x in self.lines],
            )

    def test_queue_reader_with_file(self):
        """LineReaderQueue should read lines correctly"""

        with self.testfile.open('w') as f:
            f.writelines(x + '\n' for x in self.lines)

        with self.testfile.open('r') as f:
            q = LineReaderQueue(f)
            self.assertEqual(
                self.lines,
                list(iter(q.get, None)),
            )

    def test_queues_with_cat(self):
        """Line queues should work with cat stdin/stdout"""

        with subprocess.Popen(
            ['cat'],
            cwd=str(self.tempdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        ) as proc:
            stdin = LineWriterQueue(proc.stdin)
            stdout = LineReaderQueue(proc.stdout)

            for line in self.lines:
                stdin.put(line)
            stdin.put(None)

            self.assertEqual(
                self.lines,
                list(iter(stdout.get, None)),
            )

    def test_queues_with_rev(self):
        """Line queues should work with rev stdin/stdout"""

        with subprocess.Popen(
            ['rev'],
            cwd=str(self.tempdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        ) as proc:
            stdin = LineWriterQueue(proc.stdin)
            stdout = LineReaderQueue(proc.stdout)

            for line in self.lines:
                stdin.put(line)
            stdin.put(None)

            self.assertEqual(
                self.lines,
                [x[::-1] for x in iter(stdout.get, None)],
            )


class TestProcessOnEmptyDir(TempDirTestCase):
    """Test processes running in an empty directory"""

    def test_runner_git_status(self):
        """ProcessRunner should raise on called process errors"""
        runner = ProcessRunner(['git'], workdir=str(self.tempdir))
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            runner('status', '-sb')
        self.assertIn(
            "fatal: Not a git repository",
            cm.exception.stderr,
        )

    def test_runner_git_version(self):
        """ProcessRunner should return subprocess.CompletedProcess"""
        runner = ProcessRunner(['git'], workdir=str(self.tempdir))
        proc = runner('version')
        self.assertIsInstance(proc, subprocess.CompletedProcess)
        self.assertIn('git version', proc.stdout)


class TestProcessOnEmptyAnnex(TempAnnexTestCase):
    """Test processes running in an empty git-annex repository"""

    def test_process_git_status(self):
        """Process should be able to read whole output"""
        with Process(['git', 'status'], str(self.tempdir)) as proc:
            stdout = proc.readlines(timeout=1, count=None)

        try:
            self.assertEqual(stdout, [
                'On branch master',
                '',
                'Initial commit',
                '',
                'nothing to commit (create/copy files '
                + 'and use "git add" to track)',
            ])

        except AssertionError:
            self.assertEqual(stdout, [
                'On branch master',
                '',
                'No commits yet',
                '',
                'nothing to commit (create/copy files '
                + 'and use "git add" to track)',
            ])

    def test_process_annex_metadata_batch(self):
        """Process should be able to read one line"""
        with Process(
            ['git', 'annex', 'metadata', '--batch', '--json'],
            str(self.tempdir),
        ) as proc:
            proc.writeline(
                '{"key":"SHA256E-s0--0"}'
            )
            line = proc.readline(timeout=1)
            self.assertEqual(line, ('{'
                '"command":"metadata",'
                '"note":"",'
                '"success":true,'
                '"key":"SHA256E-s0--0",'
                '"file":null,'
                '"fields":{}'
            '}'))
            line_call = proc('{"key":"SHA256E-s0--0"}')
            self.assertEqual(line_call, line)

    def test_jsonprocess_annex_metadata_batch(self):
        """JsonProcess should encode and decode properly"""
        with JsonProcess(
            ['git', 'annex', 'metadata', '--batch', '--json'],
            str(self.tempdir),
        ) as proc:
            obj = proc({'key':'SHA256E-s0--0'})
            self.assertEqual(obj, {
                'command': 'metadata',
                'note': '',
                'success': True,
                'key': 'SHA256E-s0--0',
                'file': None,
                'fields': {},
            })

    def test_process_annex_info_batch(self):
        """Process should be able to read multiple lines"""
        with Process(
            ['git', 'annex', 'info', '--batch'],
            str(self.tempdir),
        ) as proc:
            proc.writeline('here')
            lines_here = proc.readlines(timeout=1, count=2)
            self.assertEqual(lines_here, [
                'remote annex keys: 0',
                'remote annex size: 0 bytes',
            ])
            proc.writeline('.')
            lines_dot = proc.readlines(timeout=1, count=7)
            self.assertEqual(lines_dot, [
                'directory: .',
                'local annex keys: 0',
                'local annex size: 0 bytes',
                'annexed files in working tree: 0',
                'size of annexed files in working tree: 0 bytes',
                'numcopies stats: ',
                'repositories containing these files: 0',
            ])

    def test_process_matches_popen_communicate(self):
        """Process.communicate should work as Popen.communicate does"""
        with Process(
            ['git', 'config', '-l'],
            str(self.tempdir),
        ) as proc:
            result_proc = proc.communicate()

        with subprocess.Popen(
            ['git', 'config', '-l'],
            cwd=str(self.tempdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        ) as popen:
            result_popen = popen.communicate()

        self.assertEqual(result_proc, result_popen)


class TestBatchProcessesOnThreeFiles(ThreeAnnexedFilesTestCase):
    """Test git-annex batch/json processes on a three file annex"""

    def test_batch_lookupkey(self):
        """BatchProcess should work with lookupkey --batch"""
        lookupkey = GitAnnexBatchProcess(
            ['lookupkey', '--batch'],
            str(self.tempdir),
        )

        for f, k in self.keys.items():
            with self.subTest(file=f):
                self.assertEqual(lookupkey(f), k)

    def test_batchjson_metadata(self):
        """BatchJsonProcess should work with metadata --batch --json"""
        metadata = GitAnnexBatchJsonProcess(
            ['metadata', '--batch', '--json'],
            str(self.tempdir),
        )

        def meta(key, file=None):
            return {
                'command': 'metadata',
                'note': '',
                'success': True,
                'key': key,
                'file': file,
                'fields': {},
            }

        for f, k in self.keys.items():
            with self.subTest(file=f):
                self.assertEqual(metadata({'key': k}), meta(k))
                self.assertEqual(metadata({'file': f}), meta(k, f))

    def test_batchjson_restarts(self):
        """BatchJsonProcess should auto-restart dead processes"""
        metadata = GitAnnexBatchJsonProcess(
            ['metadata', '--batch', '--json'],
            str(self.tempdir),
        )

        for f, k in self.keys.items():
            with self.subTest(file=f):
                file_meta = metadata({'file': f})
                key_meta = metadata({'key': k})

                # Invalid query
                with self.assertRaises(subprocess.CalledProcessError):
                    metadata({'key': 'invalid'})

                self.assertEqual(file_meta, metadata({'file': f}))
                self.assertEqual(key_meta, metadata({'key': k}))


if __name__ == '__main__':
    unittest.main()

