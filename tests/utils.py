import tempfile
import functools
import tarfile

from git_annex_adapter import GitRepo


def with_temp_repo(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tempfile.TemporaryDirectory() as repo_path:
            repo = GitRepo(repo_path)
            return func(*args, **kwargs, repo=repo)
    return wrapper


def with_tar_repo(tar_path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tempfile.TemporaryDirectory() as repo_path:
                with tarfile.open(tar_path) as tar:
                    tar.extractall(path=repo_path)
                repo = GitRepo(repo_path)
                return func(*args, **kwargs, repo=repo)
        return wrapper
    return decorator
