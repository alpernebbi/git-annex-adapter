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
            self.commit('Initialize repo', allow_empty=True)

    def _git(self, *commands):
        return subprocess.check_output(
            ('git', *commands),
            universal_newlines=True,
            cwd=self.path,
        )

    def status(self):
        return self._git('status', '-s')

    def commit(self, message, add=True, allow_empty=False):
        command = ['commit', '-m', message]
        if add: command.append('-a')
        if allow_empty: command.append('--allow-empty')
        return self._git(*command)
