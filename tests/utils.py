import tempfile
import functools
import tarfile

from git_annex_adapter import GitRepo
from git_annex_adapter import GitAnnexRepo


def with_folder(tar_path=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tempfile.TemporaryDirectory() as temp_folder:
                if tar_path:
                    with tarfile.open(tar_path) as tar:
                        tar.extractall(path=temp_folder)
                return func(*args, **kwargs, temp_folder=temp_folder)
        return wrapper
    return decorator


def with_repo(tar_path=None, annex=False):
    def decorator(func):
        @functools.wraps(func)
        @with_folder(tar_path)
        def wrapper(*args, **kwargs):
            repo = GitRepo(kwargs['temp_folder'])
            if annex:
                GitAnnexRepo.make_annex(repo)
            del kwargs['temp_folder']

            try:
                return func(*args, **kwargs, repo=repo)
            finally:
                if annex:
                    repo.annex._annex('uninit')
        return wrapper
    return decorator
