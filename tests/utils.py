import tempfile
import functools
import tarfile
import os

from git_annex_adapter import GitRepo
from git_annex_adapter import GitAnnexRepo


def with_folder(tar_path=None, param='temp_folder'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tempfile.TemporaryDirectory() as temp_folder:
                if tar_path:
                    with tarfile.open(tar_path) as tar:
                        tar.extractall(path=temp_folder)
                kwargs[param] = temp_folder
                return func(*args, **kwargs)
        return wrapper
    return decorator


def with_repo(tar_path=None, annex=False, param='repo'):
    def decorator(func):
        @functools.wraps(func)
        @with_folder(tar_path, param='repo_path')
        def wrapper(*args, **kwargs):
            repo = GitRepo(kwargs['repo_path'])
            if annex:
                GitAnnexRepo.make_annex(repo)
            del kwargs['repo_path']
            kwargs[param] = repo
            try:
                return func(*args, **kwargs)
            finally:
                if annex:
                    repo.annex._annex('uninit')
        return wrapper
    return decorator
