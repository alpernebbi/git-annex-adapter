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
import threading
import queue

from .exceptions import NotAGitRepoError

logger = logging.getLogger(__name__)


class Process(subprocess.Popen):
    """
    Extends subprocess.Popen to talk to processes interactively.

    Overrides the following arguments for subprocess.Popen:
        stdin: subprocess.PIPE
        stdout: subprocess.PIPE
        stderr: subprocess.PIPE
        universal_newlines: True
        bufsize. 1

    Two threads continuously reading lines from stdout and stderr to
    individual queues are started as well, so these streams shouldn't
    be manually read.

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


        # https://stackoverflow.com/a/4896288
        self._queues = {
            'stdout': queue.Queue(),
            'stderr': queue.Queue(),
        }

        self._threads = {
            'stdout': threading.Thread(
                target=self._enqueue_lines,
                args=(self.stdout, self._queues['stdout']),
                daemon=True,
            ),
            'stderr': threading.Thread(
                target=self._enqueue_lines,
                args=(self.stderr, self._queues['stderr']),
                daemon=True,
            ),
        }

        for thread in self._threads.values():
            thread.start()

    @staticmethod
    def _enqueue_lines(src, q):
        """Read lines from a source and put them into a queue."""
        with src:
            for line in iter(src.readline, ''):
                q.put(line.strip())

    @staticmethod
    def _unqueue(q, timeout=0.1):
        """Yield items from a queue within a timeout."""
        try:
            # This is assuming the process will not wait while
            # printing the lines, so the queue will have all
            # relevant output when we get the first line
            yield q.get(block=True, timeout=timeout)
            yield from iter(q.get_nowait, queue.Empty)
        except queue.Empty:
            pass

    def communicate_lines(self, input=None, timeout=0.1):
        """
        Send a line to stdin, read and return lines from stdout.

        This waits at most timeout seconds for the first line to
        arrive from the output, then returns all immediately available
        output lines as a list.
        """
        if input is not None:
            print(input, file=self.stdin, flush=True)

        outputs = list(self._unqueue(
            self._queues['stdout'],
            timeout=timeout,
        ))

        if len(outputs) == 0:
            fmt = "Command {} with input '{}' " \
                + "timed out after {} seconds."
            msg = fmt.format(self.args, input, timeout)
            raise subprocess.TimeoutExpired(self.args, timeout) from \
                TimeoutError(msg)
        else:
            return outputs

    def communicate(self, input=None, timeout=0.1):
        """
        Interact with the process without terminating it.

        Instead of returning stdout as a list (see communicate_lines),
        this function joins the lines with newline characters. Returns
        a tuple (stdout_data, stderr_data) for Popen.communicate()
        compatibility.
        """
        try:
            stdout = '\n'.join(
                self.communicate_lines(input=input, timeout=timeout)
            ) + '\n'
        except subprocess.TimeoutExpired:
            stdout = ''

        stderr = '\n'.join(self._unqueue(self._queues['stderr']))
        stderr += '\n' if stderr else ''

        return (stdout, stderr)

    def __exit__(self, exc_type, exc_value, traceback):
        # The process would deadlock if it is waiting for input
        self.stdin.close()
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

