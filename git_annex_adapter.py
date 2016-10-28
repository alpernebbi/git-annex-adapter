import functools
import subprocess
import os
import json


class GitRepo:
    def __init__(self, path):
        self.path = path

        if not os.path.isdir(self.path):
            print("Creating directory {}".format(self.path))
            os.makedirs(self.path)

        if not os.path.isdir(os.path.join(self.path, '.git')):
            print("Initializing git repo at {}".format(self.path))
            self._git('init')

        if 'master' not in self.branches:
            self.checkout('master')
            self.commit('Initialize repo', allow_empty=True)

    def _git(self, *commands):
        return subprocess.check_output(
            ('git', *commands),
            universal_newlines=True,
            cwd=self.path,
        )

    @property
    def status(self):
        return self._git('status', '-s')

    @property
    def branches(self):
        branch_list = []
        current_exists = False
        for branch in self._git('branch', '--list').splitlines():
            if branch[0] == '*':
                branch_list.insert(0, branch[2:])
                current_exists = True
            else:
                branch_list.append(branch[2:])
        if branch_list and not current_exists:
            raise RuntimeError(
                'No current branch found among: \n'
                '    {}\n    in {}'.format(branch_list, self.path))
        return tuple(branch_list)

    def checkout(self, branch, new_branch=True):
        command = ['checkout', branch]
        if new_branch and branch not in self.branches:
            command.insert(1, '-b')
        return self._git(*command)

    def commit(self, message, add=True, allow_empty=False):
        command = ['commit', '-m', message]
        if add: command.append('-a')
        if allow_empty: command.append('--allow-empty')
        return self._git(*command)

    def cherry_pick(self, branch):
        return self._git("cherry-pick", branch)

    def stash(self, pop=False):
        command = ['stash']
        if pop: command.append('pop')
        return self._git(*command)

    def move(self, src, dest, overwrite=False, merge=True):
        abs_src = os.path.join(self.path, src)
        abs_dest = os.path.join(self.path, dest)

        if os.path.isdir(abs_src) and os.path.isdir(abs_dest) and merge:
            for src_ in files_in(abs_src, relative=self.path):
                dest_ = os.path.join(dest, os.path.relpath(src_, src))
                self.move(src_, dest_, overwrite=overwrite)
        elif os.path.isfile(abs_dest):
            if os.path.samefile(abs_src, abs_dest) or overwrite:
                self._git('rm', dest)
                dest_dir = os.path.dirname(dest)
                abs_dest_dir = os.path.join(self.path, dest_dir)
                os.makedirs(abs_dest_dir, exist_ok=True)
                self._git('mv', src, dest)
            else:
                raise ValueError(
                    "Destination {} already exists.".format(dest))
        else:
            self._git('mv', src, dest)


    @property
    def tree_hash(self):
        commit = self._git('cat-file', 'commit', 'HEAD').split()
        return commit[commit.index('tree') + 1]


class GitAnnexRepo(GitRepo):
    def __init__(self, path):
        super().__init__(path)
        self.annex = GitAnnex(self)
        self.annex.meta = GitAnnexRepoMetadata(self)

    @classmethod
    def make_annex(cls, repo):
        repo.annex = GitAnnex(repo)
        repo.annex.meta = GitAnnexRepoMetadata(repo)
        repo.__class__ = cls


class GitAnnex:
    def __init__(self, repo):
        self.repo = repo
        self._annex = functools.partial(repo._git, 'annex')

        if not os.path.isdir(os.path.join(repo.path, '.git', 'annex')):
            print("Initializing git-annex at {}".format(repo.path))
            self._annex('init', 'albumin')

    def import_(self, path, duplicate=True):
        command = ['import', path]
        if duplicate: command.append('--duplicate')
        return self._annex(*command)

    def calckey(self, file_path):
        return self._annex('calckey', file_path).rstrip()

    def locate(self, key):
        return self._annex('contentlocation', key).rstrip()


class GitAnnexRepoMetadata:
    def __init__(self, repo):
        self.repo = repo
        self._program = None
        self._start()

    def _start(self):
        self._program = subprocess.Popen(
            ["git", "annex", "metadata", "--batch", "--json"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self.repo.path,
        )

    def _query(self, **query):
        json_ = json.dumps(query)
        print(json_, file=self._program.stdin, flush=True)
        response = self._program.stdout.readline()
        return json.loads(response)

    @property
    def _running(self):
        return self._program and self._program.poll() is None

    def _stop(self, kill=False):
        return self._program.terminate()


def files_in(dir_path, relative=False):
    exclude = ['.git']
    for root, dirs, files in os.walk(dir_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        if relative:
            root = os.path.relpath(root, start=relative)
        for f in files:
            yield os.path.join(root, f)
