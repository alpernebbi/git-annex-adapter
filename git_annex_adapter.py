import subprocess


class GitRepo:
    def __init__(self, path):
        self.path = path

    def _git(self, *commands):
        return subprocess.check_output(
            ('git', *commands),
            universal_newlines=True,
            cwd=self.path,
        )
