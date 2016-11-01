import functools
import subprocess
import os
import json
import collections.abc
from datetime import datetime


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
            return

        if os.path.isfile(abs_dest):
            if os.path.samefile(abs_src, abs_dest) or overwrite:
                self._git('rm', dest)
            else:
                raise ValueError(
                    "Destination {} already exists.".format(dest))

        abs_dest_dir = os.path.dirname(abs_dest)
        os.makedirs(abs_dest_dir, exist_ok=True)
        self._git('mv', src, dest)

        abs_src_dir = os.path.dirname(abs_src)
        if not os.listdir(abs_src_dir):
            os.removedirs(abs_src_dir)


    @property
    def tree_hash(self):
        commit = self._git('cat-file', 'commit', 'HEAD').split()
        return commit[commit.index('tree') + 1]

    def __repr__(self):
        return 'GitRepo(path={!r})'.format(self.path)


class GitAnnexRepo(GitRepo):
    def __init__(self, path):
        super().__init__(path)
        self.annex = GitAnnex(self)

    @classmethod
    def make_annex(cls, repo):
        repo.annex = GitAnnex(repo)
        repo.__class__ = cls

    def __repr__(self):
        return 'GitAnnexRepo(path={!r})'.format(self.path)


class GitAnnex(collections.abc.Mapping):
    def __init__(self, repo):
        self.repo = repo
        self._annex = functools.partial(repo._git, 'annex')

        if not os.path.isdir(os.path.join(repo.path, '.git', 'annex')):
            print("Initializing git-annex at {}".format(repo.path))
            self._annex('init', 'albumin')

    def import_(self, path, duplicate=True):
        if os.path.basename(path) in os.listdir(self.repo.path):
            raise ValueError('Import path basename conflict')
        command = ['import', path]
        if duplicate: command.append('--duplicate')
        return self._annex(*command)

    def calckey(self, file_path):
        return self._annex('calckey', file_path).rstrip()

    def locate(self, key):
        return self._annex('contentlocation', key).rstrip()

    @property
    def keys(self):
        jsons = self._annex('metadata', '--all', '--json').splitlines()
        meta_list = [json.loads(json_) for json_ in jsons]
        return {meta['key'] for meta in meta_list}

    @property
    def files(self):
        jsons = self._annex('metadata', '--json').splitlines()
        meta_list = [json.loads(json_) for json_ in jsons]
        return {meta['file']: meta['key'] for meta in meta_list}

    def __getitem__(self, key):
        if key in self.keys:
            return GitAnnexMetadata(self, key)
        else:
            raise KeyError("Key {} not in annex.".format(key))

    def __contains__(self, key):
        return key in self.keys

    def __iter__(self):
        yield from self.keys

    def __len__(self):
        return len(self.keys)

    def __repr__(self):
        return 'GitAnnex(repo={!r})'.format(self.repo)


class GitAnnexMetadata(collections.abc.MutableMapping):
    def __init__(self, annex, key):
        self.key = key
        self.annex = annex
        self._meta = functools.partial(
            annex._annex, 'metadata', '--key', key)

    def __getitem__(self, meta_key):
        values = self._meta('-g', meta_key).splitlines()
        return_value = set(values)

        for v in return_value:
            try:
                dt_obj = datetime.strptime(v, '%Y-%m-%d@%H-%M-%S')
                return_value.remove(v)
                return_value.add(dt_obj)
            except (ValueError, TypeError):
                continue

        if len(return_value) == 1:
            return return_value.pop()
        else:
            return return_value

    def __setitem__(self, meta_key, value):
        old_value = self[meta_key]
        if not isinstance(value, set):
            value = {value}
        if not isinstance(old_value, set):
            old_value = {old_value}

        for v in value:
            if isinstance(v, datetime):
                dt_str = v.strftime('%Y-%m-%d@%H-%M-%S')
                value.remove(v)
                value.add(dt_str)

        cmds = []
        for v in value - old_value:
            cmds += ['-s', '{}+={}'.format(meta_key, v)]
        for v in old_value - value:
            cmds += ['-s', '{}-={}'.format(meta_key, v)]
        self._meta(*cmds)

    def __delitem__(self, meta_key):
        self._meta('-r', meta_key)

    def __contains__(self, meta_key):
        return self[meta_key] > set()

    def __iter__(self):
        json_ = self._meta('--json')
        fields = json.loads(json_)['fields']
        yield from fields.keys()

    def __len__(self):
        len([x for x in self])

    def __repr__(self):
        repr_ = 'GitAnnexFileMetadata(key={!r}, path={!r})'
        return repr_.format(self.key, self.annex.repo.path)


def files_in(dir_path, relative=False):
    exclude = ['.git']
    for root, dirs, files in os.walk(dir_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        if relative:
            root = os.path.relpath(root, start=relative)
        for f in files:
            yield os.path.join(root, f)
