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

    def _git(self, *commands):
        return subprocess.check_output(
            ('git', *commands),
            universal_newlines=True,
            cwd=self.path,
        )
