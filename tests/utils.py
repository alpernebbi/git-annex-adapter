import tempfile
import functools
import tarfile

from git_annex_adapter import GitRepo
from git_annex_adapter import GitAnnexRepo


def with_temp_folder(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tempfile.TemporaryDirectory() as temp_folder:
            return func(*args, **kwargs, temp_folder=temp_folder)
    return wrapper


def from_tar(tar_path=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tarfile.open(tar_path) as tar:
                tar.extractall(path=kwargs['temp_folder'])
            return func(*args, **kwargs)

        if tar_path:
            return wrapper
        else:
            return func
    return decorator


def with_repo(tar_path=None, annex=False):
    def decorator(func):
        @functools.wraps(func)
        @with_temp_folder
        @from_tar(tar_path)
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
