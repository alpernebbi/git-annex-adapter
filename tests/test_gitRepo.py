from unittest import TestCase
import tempfile
import functools

from git_annex_adapter import GitRepo


def with_temp_repo(test_f):
    @functools.wraps(test_f)
    def new_test_f(*args, **kwargs):
        with tempfile.TemporaryDirectory() as repo_path:
            repo = GitRepo(repo_path)
            test_f(*args, **kwargs, repo=repo)
    return new_test_f


class TestGitRepo(TestCase):
    @with_temp_repo
    def test_git(self, repo):
        repo._git('--version')
