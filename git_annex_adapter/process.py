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

import itertools
import json
import logging
import subprocess
import threading
import queue

from .exceptions import NotAGitRepoError

logger = logging.getLogger(__name__)


class ResizableQueue(queue.Queue):
    """
    Extends queue.Queue to enable changing its maxsize.

    """
    def resize(self, maxsize):
        """
        Change the maximum size of the queue.

        Doesn't remove any items, so might cause qsize() > maxsize.
        Shouldn't cause a problem since put() checks this condition,
        """
        with self.mutex:
            self.maxsize = maxsize


class Process(subprocess.Popen):
    """
    Extends subprocess.Popen to implement non-blocking read and writes.

    Overrides the following arguments for subprocess.Popen:
        stdin: subprocess.PIPE
        stdout: subprocess.PIPE
        stderr: subprocess.PIPE
        universal_newlines: True
        bufsize. 1

    Threads continuously reading lines from stdout and stderr and
    writing lines to stdin from/to individual queues are started as
    well, so these streams shouldn't be manually read.

    """
    def __init__(self, args, workdir, **kwargs):
        kwargs.update({
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "universal_newlines": True,
            "bufsize": 1,
            "cwd": workdir,
        })
        super().__init__(args, **kwargs)
        self.workdir = workdir


        # https://stackoverflow.com/a/4896288
        self._queues = {
            'stdin': ResizableQueue(),
            'stdout': ResizableQueue(),
            'stderr': ResizableQueue(),
        }

        self._threads = {
            'stdin': threading.Thread(
                target=self._write_lines_from_queue,
                args=(self._queues['stdin'], self.stdin),
                daemon=True,
            ),
            'stdout': threading.Thread(
                target=self._read_lines_to_queue,
                args=(self.stdout, self._queues['stdout']),
                daemon=True,
            ),
            'stderr': threading.Thread(
                target=self._read_lines_to_queue,
                args=(self.stderr, self._queues['stderr']),
                daemon=True,
            ),
        }

        for thread in self._threads.values():
            thread.start()

    @staticmethod
    def _read_lines_to_queue(src, q):
        """Read lines from a source and put them into a queue."""
        with src:
            for line in iter(src.readline, ''):
                q.put(line.strip())

        q.resize(1)
        while True:
            q.put(None)

    @staticmethod
    def _write_lines_from_queue(q, dest):
        """Write lines from a queue to a file."""
        with dest:
            for line in iter(q.get, None):
                print(line, file=dest, flush=True)

    def writeline(self, line):
        """
        Send a line to be printed to stdin.

        None is interpreted as an EOF, and closes the stream.
        """
        t = self._threads['stdin']
        if not t.isAlive():
            fmt = "Reader thread {} for stdin of command {} is dead."
            msg = fmt.format(t, self.args)
            raise BrokenPipeError(msg)
        self._queues['stdin'].put(line)

    def writelines(self, lines):
        """
        Send multiple lines to be printed to stdin.

        This only calls self.writeline with each item of an iterable.
        """
        for line in lines:
            self.writeline(line)

    def readline(self, timeout=0, source='stdout'):
        """
        Return a line from either stdout or stderr.

        This method will wait at most timeout seconds to retrieve
        one line from the source. If timeout is None, it will wait
        until a line has been read, which may cause a deadlock. If
        there are certainly no more lines to read, returns None.

        If the timeout is exceeded, raises a TimeoutError.
        """
        q = self._queues[source]

        try:
            if timeout == 0:
                return q.get(block=False)
            else:
                return q.get(block=True, timeout=timeout)

        except queue.Empty as err:
            fmt = "{} of command {} timed out after {} seconds"
            msg = fmt.format(source, self.args, timeout)
            raise TimeoutError(msg) from err

    def readlines(self, timeout=0, source='stdout', count=None):
        """
        Reads an exact number of lines from stdout or stderr.

        This method will wait for, read and return at most count
        number of lines. A None count is interpred as unlimited.

        If timeout is not None, this waits at most timeout seconds
        for any individual line; which means this method can block
        about timeout * count seconds. The returned list may be
        shorter than count lines if timeout exceeds.
        """
        q = self._queues[source]

        def readline():
            return self.readline(timeout=timeout, source=source)

        output = []
        try:
            for line in itertools.islice(iter(readline, None), count):
                output.append(line)
        except TimeoutError:
            pass
        return output

    def communicate(self, input=None, timeout=0.1):
        """
        Interact with the process without terminating it.

        Instead of returning stdout as a list (see communicate_lines),
        this function joins the lines with newline characters. Returns
        a tuple (stdout_data, stderr_data) for Popen.communicate()
        compatibility.
        """
        if input is not None:
            self.writelines(l.strip() for l in input.splitlines())

        outs = self.readlines(
            timeout=timeout,
            source='stdout',
            count=None,
        )
        stdout = ('\n'.join(outs) + '\n') if outs else ''

        errs = self.readlines(
            timeout=0,
            source='stderr',
            count=None,
        )
        stderr = ('\n'.join(errs) + '\n') if errs else ''

        return (stdout, stderr)

    def __call__(self, line):
        """
        Write a line to stdin, read and return a line from stdout.

        This method blocks until an output line is available.
        """
        self.writeline(line)
        return self.readline(timeout=None)

    def __exit__(self, exc_type, exc_value, traceback):
        # The process would deadlock if it is waiting for input
        try:
            self.writeline(None)
        except BrokenPipeError:
            pass

        super().__exit__(exc_type, exc_value, traceback)

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args={
                "args": self.args,
                "workdir": self.workdir,
            }
        )


class JsonProcess(Process):
    """
    Extends Process so that it can translate dictionary objects to and
    from json formatted lines to be written to or read from a process.

    """
    def readjson(self, timeout=0, source='stdout'):
        """
        Read a json formatted line from source and return it as a
        dictionary object.
        """
        line = self.readline(timeout=timeout, source=source)

        try:
            return json.loads(line)
        except TypeError:
            return line

    def writejson(self, obj):
        """
        Encode a dictionary object as a json formatted line and
        write it to the stdin.
        """
        line = json.dumps(obj)
        return self.writeline(line)

    def __call__(self, obj):
        """
        Write a dictionary object to the stdin as a json formatted
        line, decode and return lines from stdout as dictionary
        objects.
        """
        self.writejson(obj)
        return self.readjson(timeout=None)


class ProcessRunner:
    """
    Helper class to repeatedly run a program with different arguments

    git_proc = ProcessRunner(['git'], workdir='/path/to/repo')
    result = git_proc('status', '-sb')
    print(result.stdout)

    """
    def __init__(self, args_prefix, workdir):
        self.args_prefix = args_prefix
        self.workdir = workdir
        self.logger = logging.getLogger('{name}.{cls}'.format(
            name=__name__,
            cls=self.__class__.__name__,
        ))

    def __call__(self, *args_suffix):
        return subprocess.run(
            (*self.args_prefix, *args_suffix),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self.workdir,
            check=True,
        )

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args={
                "args_prefix": self.args_prefix,
                "workdir": self.workdir,
            }
        )


class GitAnnexRunner(ProcessRunner):
    """Helper class to run git-annex commands."""
    def __init__(self, args_prefix, workdir):
        args_prefix = ('git-annex', *args_prefix)
        super().__init__(args_prefix, workdir)

    def __call__(self, *args_suffix):
        try:
            return super().__call__(*args_suffix)

        except FileNotFoundError as err:
            if "No such file or directory:" in err.strerror:
                fmt = "Path '{}' does not exist."
                msg = fmt.format(self.workdir)
                raise NotAGitRepoError(msg) from err
            else:
                raise

        except subprocess.CalledProcessError as err:
            if "git-annex: Not in a git repository" in err.stderr:
                fmt = "Path '{}' is not in a git repository."
                msg = fmt.format(self.workdir)
                raise NotAGitRepoError(msg) from err
            else:
                raise


class GitAnnexInitRunner(GitAnnexRunner):
    """Helper class to run git-annex init commands."""
    def __init__(self, workdir):
        super().__init__(['init'], workdir)

    def __call__(self, description=None, version=None):
        args = []
        if description is not None:
            args.append(description)
        if version is not None:
            args.append('--version={}'.format(version))

        try:
            return super().__call__(*args)

        except subprocess.CalledProcessError as err:
            if "option --version:" in err.stderr:
                fmt = "Repository version '{}' is invalid."
                msg = fmt.format(version)
                raise ValueError(msg) from err
            else:
                self.logger.debug("Unknown error:\n", exc_info=True)
                self.logger.debug("stderr:\n{}".format(err.stderr))
                raise
 
        except:
            self.logger.debug("Unknown error:\n", exc_info=True)
            raise


class GitAnnexVersionRunner(GitAnnexRunner):
    """Helper class to run git-annex version commands."""
    def __init__(self, workdir):
        super().__init__(['version'], workdir)

    def __call__(self, raw=False):
        args = []
        if raw:
            args.append('--raw')

        try:
            return super().__call__(*args)

        except subprocess.CalledProcessError as err:
            self.logger.debug("Unknown error:\n", exc_info=True)
            self.logger.debug("stderr:\n{}".format(err.stderr))
            raise

        except:
            self.logger.debug("Unknown error:\n", exc_info=True)
            raise

