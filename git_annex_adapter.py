import subprocess
import os


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

    def status(self):
        return self._git('status', '-s')

    @property
    def branches(self):
        branch_list = self._git('branch', '--list').split()
        if '*' in branch_list:
            current_branch = branch_list[branch_list.index('*') + 1]
            branch_list.remove('*')
            branch_list.remove(current_branch)
            branch_list.insert(0, current_branch)
        return tuple(branch_list)

    def checkout(self, branch):
        command = ['checkout', branch]
        if branch not in self.branches: command.insert(1, '-b')
        return self._git(*command)

    def commit(self, message, add=True, allow_empty=False):
        command = ['commit', '-m', message]
        if add: command.append('-a')
        if allow_empty: command.append('--allow-empty')
        return self._git(*command)

    def tree_hash(self):
        commit = self._git('cat-file', 'commit', 'HEAD').split()
        return commit[commit.index('tree') + 1]
