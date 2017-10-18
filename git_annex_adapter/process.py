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

import collections
import itertools
import json
import logging
import subprocess
import threading
import queue

from .exceptions import NotAGitRepoError

logger = logging.getLogger(__name__)


class LineReaderQueue(queue.Queue):
    """
    Extends Queue to continuously read lines from a source to itself.

    """
    def __init__(self, src):
        super().__init__()
        self.src = src
        self._thread = threading.Thread(
            target=self._reader,
            args=(),
            daemon=True,
        )
        self._thread.start()

    def _reader(self):
        """Read lines from this queue's source into the queue."""
        try:
            with self.src:
                for line in iter(self.src.readline, ''):
                    self.put(line.rstrip('\n'))
        finally:
            self.put(None)

    def get(self, block=True, timeout=None):
        """
        Remove and return a line from the queue.

        If the reader thread is dead and there's no more lines to
        return, raises BrokenPipeError.
        """
        with self.mutex:
            if not self._thread.is_alive() and self._qsize() == 0:
                fmt = 'Reader thread for {} is dead.'
                msg = fmt.format(self.src)
                raise BrokenPipeError(msg)

        item = super().get(block=block, timeout=timeout)

        # A None means the thread is about to die, so wait until
        # it dies to prevent a race condition.
        if item is None:
            self._thread.join()

        return item

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.src
        )


class LineWriterQueue(queue.Queue):
    """
    Extends Queue to automatically write lines from itself to a
    destination.

    """
    def __init__(self, dest):
        super().__init__()
        self.dest = dest
        self._thread = threading.Thread(
            target=self._writer,
            args=(),
            daemon=True,
        )
        self._thread.start()

    def _writer(self):
        """Write lines from this queue to it's destination file."""
        with self.dest:
            for line in iter(self.get, None):
                print(line, file=self.dest, flush=True)


    def put(self, item, block=True, timeout=None):
        """
        Put an item into the queue.

        If the writer thread is dead, raises a BrokenPipeError
        regardless of the arguments.
        """
        with self.mutex:
            if not self._thread.is_alive():
                fmt = "Writer thread for {} is dead."
                msg = fmt.format(self.dest)
                raise BrokenPipeError(msg)

        super().put(item, block=block, timeout=timeout)

        # A None will kill the thread, so wait until the thread dies
        # to prevent a race condition.
        if item is None:
            self._thread.join()

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args=self.dest
        )


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

        Queues = collections.namedtuple(
            'Queues',
            ['stdin', 'stdout', 'stderr'],
        )

        self._queues = Queues(
            stdin=LineWriterQueue(self.stdin),
            stdout=LineReaderQueue(self.stdout),
            stderr=LineReaderQueue(self.stderr),
        )

    def writeline(self, line):
        """
        Send a line to be printed to stdin.

        None is interpreted as an EOF, and closes the stream.
        """
        try:
            self._queues.stdin.put(line, block=False, timeout=0)

        except BrokenPipeError:
            fmt = "Writer thread for stdin of command {} is dead."
            msg = fmt.format(self.args)
            raise BrokenPipeError(msg)

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
        if source == 'stdout':
            q = self._queues.stdout
        elif source == 'stderr':
            q = self._queues.stderr
        elif source == 'stdin':
            q = self._queues.stdin

        try:
            if timeout == 0:
                return q.get(block=False)
            else:
                return q.get(block=True, timeout=timeout)

        except queue.Empty as err:
            fmt = "{} of command {} timed out after {} seconds"
            msg = fmt.format(source, self.args, timeout)
            raise TimeoutError(msg) from err

        except BrokenPipeError as err:
            fmt = 'Reader thread for {} of command {} is dead.'
            msg = fmt.format(source, self.args)
            raise BrokenPipeError(msg) from err

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
        def readline():
            return self.readline(timeout=timeout, source=source)

        output = []
        try:
            for line in itertools.islice(iter(readline, None), count):
                output.append(line)

        except TimeoutError:
            pass

        except BrokenPipeError:
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
            lines = (l.rstrip('\n') for l in input.splitlines())
            self.writelines(lines)

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

    def check(self):
        """
        Check if the process has exited, and if an error occured.

        Returns None if process hasn't exited, or a CompletedProcess
        object if it has exited without an error. If the process
        has exited with an error, raises a CalledProcessError.

        If process has exited, all available stdout and stderr
        are captured into the returned object or raised exception.
        """
        retcode = self.poll()

        if retcode is not None:
            stdout, stderr = self.communicate(timeout=0)
            completed = subprocess.CompletedProcess(
                args=self.args,
                returncode=retcode,
                stdout=stdout,
                stderr=stderr,
            )
            completed.check_returncode()
            return completed

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

        if line is not None and line != 'null':
            return json.loads(line)
        else:
            return line

    def writejson(self, obj):
        """
        Encode a dictionary object as a json formatted line and
        write it to the stdin.
        """
        if obj is not None:
            line = json.dumps(obj)
        else:
            line = None

        return self.writeline(line)

    def __call__(self, obj):
        """
        Write a dictionary object to the stdin as a json formatted
        line, decode and return lines from stdout as dictionary
        objects.
        """
        self.writejson(obj)
        return self.readjson(timeout=None)


class GitAnnexBatchProcess:
    """
    Helper class to run git-annex processes in batch mode.

    Starts a Process instance when necessary, and passes method
    calls to it. If the Process instance dies, restarts it.

    """
    _procclass = Process

    def __init__(self, args, workdir):
        self.args = ('git', 'annex', *args)
        self.workdir = workdir
        self._process = None
        self._dead_process = None

    @property
    def process(self):
        if self._process and self._process.poll() is None:
            return self._process

        try:
            new_process = self._procclass(self.args, self.workdir)
            new_process.check()

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

        if self._process:
            # Copy remaining stdin lines
            stdin = self._process.readlines(source='stdin')
            new_process.writelines(stdin)
            self._dead_process = self._process

        self._process = new_process
        return self._process

    def __call__(self, line):
        p = self.process
        output = p(line)

        try:
            # Stdout closed, process should die soon.
            if output is None:
                p.wait()

            done = p.check()

        except subprocess.CalledProcessError as err:
            # Process just died, but the stdin thread is waiting
            # for a new value. Send None to close it.
            p.writeline(None)
            raise

        if line is not None and done:
            # Exited normally without a non-EOF input. Why?
            logger.debug('Process %s exited with input line.', p)
            logger.debug('stdin:\n%s', line)
            logger.debug('stdout:\n%s\n%s', output, done.stdout)
            logger.debug('stderr:\n%s', done.stderr)

            # Close stdin thread just in case.
            p.writeline(None)

        return output

    def __repr__(self):
        return "{name}.{cls}({args})".format(
            name=__name__,
            cls=self.__class__.__name__,
            args={
                "args": self.args,
                "workdir": self.workdir,
            }
        )


class GitAnnexBatchJsonProcess(GitAnnexBatchProcess):
    """
    Helper class to run git-annex processes in batch json mode.

    Starts a JsonProcess instance when necessary, and passes method
    calls to it. If the Process instance dies, restarts it.

    """
    _procclass = JsonProcess


class GitAnnexMetadataBatchJsonProcess(GitAnnexBatchJsonProcess):
    """
    Helper class that interacts with git-annex metadata --batch --json.

    """
    def __init__(self, workdir):
        super().__init__(['metadata', '--batch', '--json'], workdir)

    def __call__(self, key=None, file=None, fields=None):
        """
        Sends a json command to the process, and returns the output.

        *key* should be a git-annex internal key. *file* should be a
        relative path to a file in the worktree. *fields* should be
        a dict from strings to lists of strings.

        All given fields are directly passed to the process without
        validation.
        """
        query = {}
        if key is not None:
            query['key'] = key
        if file is not None:
            query['file'] = file
        if fields is not None:
            query['fields'] = fields

        try:
            return super().__call__(query)

        except subprocess.CalledProcessError as err:
            logger.debug("Unknown error:\n", exc_info=True)
            logger.debug("stderr:\n{}".format(err.stderr))
            raise

        except:
            logger.debug("Unknown error:\n", exc_info=True)
            raise


class GitAnnexContentlocationBatchProcess(GitAnnexBatchProcess):
    """
    Helper class that interacts with git-annex contentlocation --batch.

    """
    def __init__(self, workdir):
        super().__init__(['contentlocation', '--batch'], workdir)

    def __call__(self, key):
        """
        Sends a git-annex key to the process, and returns the output.
        """
        try:
            return super().__call__(key)

        except subprocess.CalledProcessError as err:
            logger.debug("Unknown error:\n", exc_info=True)
            logger.debug("stderr:\n{}".format(err.stderr))
            raise

        except:
            logger.debug("Unknown error:\n", exc_info=True)
            raise


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

        except NotAGitRepoError:
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

