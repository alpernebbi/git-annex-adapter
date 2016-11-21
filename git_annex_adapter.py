import functools
import subprocess
import os
import json
import collections.abc
from argparse import Namespace


class GitRepo:
    @staticmethod
    def init_path(path):
        git = RepeatedProcess('git', workdir=path)

        if not os.path.isdir(path):
            print("Creating directory {}".format(path))
            os.makedirs(path)

        if not os.path.isdir(os.path.join(path, '.git')):
            print("Initializing git repo at {}".format(path))
            git('init')
            git('checkout', '-b', 'master')
            git('commit', '-m', 'Initialize repo', '--allow-empty')

    def __init__(self, path, create=False):
        if create:
            self.init_path(path)

        git = RepeatedProcess('git', workdir=path)
        root_path = git('rev-parse', '--show-toplevel').strip()

        git._workdir = root_path
        self.path = root_path
        self._git = git

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

    def add(self, path):
        return self._git('add', path)

    def rm(self, path):
        return self._git('rm', '-rf', path)

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

    @property
    def tree_hash(self):
        commit = self._git('cat-file', 'commit', 'HEAD').split()
        return commit[commit.index('tree') + 1]

    def __repr__(self):
        return 'GitRepo(path={!r})'.format(self.path)


class GitAnnexRepo(GitRepo):
    def __init__(self, path, create=False):
        super().__init__(path, create=create)
        self.annex = GitAnnex(self, create=create)

    @classmethod
    def make_annex(cls, repo, create=False):
        repo.annex = GitAnnex(repo, create=create)
        repo.__class__ = cls

    def __repr__(self):
        return 'GitAnnexRepo(path={!r})'.format(self.path)


class GitAnnex(collections.abc.Mapping):
    @staticmethod
    def init_path(path, description=None):
        GitRepo.init_path(path)

        annex = RepeatedProcess('git', 'annex', workdir=path)
        if not os.path.isdir(os.path.join(path, '.git', 'annex')):
            print("Initializing git-annex at {}".format(path))
            annex('init', description if description else '')

    def __init__(self, repo, create=False):
        if create:
            self.init_path(repo.path)

        self.repo = repo
        self._annex = RepeatedProcess(
            'git', 'annex',
            workdir=repo.path
        )

        self.processes = Namespace()
        batch_processes = {
            'metadata': ('metadata', '--batch', '--json'),
            'calckey': ('calckey', '--batch'),
            'lookupkey': ('lookupkey', '--batch'),
            'contentlocation': ('contentlocation', '--batch')
        }

        for proc, cmd in batch_processes.items():
            vars(self.processes)[proc] = BatchProcess(
                'git', 'annex', *cmd, workdir=repo.path
            )

        self._meta_cache = [None, None]

    def import_(self, path, duplicate=True):
        if os.path.basename(path) in os.listdir(self.repo.path):
            raise ValueError('Import path basename conflict')
        command = ['import', path]
        if duplicate: command.append('--duplicate')
        return self._annex(*command)

    def calckey(self, file_path):
        return self.processes.calckey(file_path)

    def fromkey(self, key, file_path):
        return self._annex('fromkey', key, file_path)

    def lookupkey(self, file_path):
        return self.processes.lookupkey(file_path)

    def locate(self, key, absolute=False):
        rel_path = self.processes.contentlocation(key)
        if absolute:
            return os.path.join(self.repo.path, rel_path)
        else:
            return rel_path

    def clear_metadata_cache(self):
        self._meta_cache = [None, None]

    def metadata(self, all_keys=False, cached=False):
        if cached and self._meta_cache[all_keys]:
            return self._meta_cache[all_keys]

        try:
            jsons = self._annex(
                'metadata', '--json', ('--all' if all_keys else '')
            ).splitlines()
            metadata = [json.loads(json_) for json_ in jsons]
            self._meta_cache[all_keys] = metadata
            return metadata
        except subprocess.CalledProcessError as err:
            self._meta_cache = [None, None]
            return []

    def keys(self, absent=False, cached=False):
        all_meta = self.metadata(all_keys=True, cached=cached)
        all_keys = {meta['key'] for meta in all_meta}
        if absent:
            file_meta = self.metadata(cached=cached)
            file_keys = {meta['key'] for meta in file_meta}
            return all_keys - file_keys
        else:
            return all_keys

    def files(self, cached=False):
        file_meta = self.metadata(cached=cached)
        return {meta['file'] for meta in file_meta}

    def fields(self, cached=False):
        metadata = self.metadata(all_keys=True, cached=cached)
        fields = [meta.get('fields', {}) for meta in metadata]
        return filter(
            lambda f: not f.endswith('lastchanged'),
            set.union(*map(set, fields + [{}]))
        )

    def __getitem__(self, map_key):
        if map_key in self.files(cached=True):
            key, file = self.lookupkey(map_key), map_key

        elif map_key in self.keys(cached=True):
            key, file = map_key, None

        else:
            raise KeyError(map_key)

        return GitAnnexMetadata(self, key=key, file=file)

    def __contains__(self, map_key):
        return map_key in self.keys(cached=True)

    def __iter__(self):
        yield from self.keys(cached=True)

    def __len__(self):
        return len(self.keys(cached=True))

    def __repr__(self):
        return 'GitAnnex(repo={!r})'.format(self.repo)


class GitAnnexMetadata(collections.abc.MutableMapping):
    def __init__(self, annex, key, file=None):
        self.key = key
        self.file = file
        self.annex = annex
        self.query = functools.partial(
            self.annex.processes.metadata, key=self.key
        )
        self.fields_cache = None

    def fields(self, **fields):
        if self.fields_cache and not fields:
            return self.fields_cache

        new_fields = self.query(fields=fields).get('fields', {})

        for field, value in fields.items():
            new_value = new_fields.get(field, [])
            if set(new_value) != set(value):
                self.annex.processes.metadata.restart()
                new_fields = self.query(fields=fields).get('fields', {})
                break
        else:
            self.fields_cache = new_fields
            return new_fields

        for field, value in fields.items():
            new_value = new_fields.get(field, [])
            if set(new_value) != set(value):
                self.fields_cache = None
                raise KeyError(field)
        else:
            self.fields_cache = new_fields
            return new_fields

    def locate(self, absolute=False):
        rel_path = self.annex.processes.contentlocation(self.key)
        if absolute:
            return os.path.join(self.annex.repo.path, rel_path)
        else:
            return rel_path

    def __getitem__(self, meta_key):
        if meta_key == 'key':
            return [self.key]
        if meta_key == 'file':
            return [self.file]
        values = self.fields().get(meta_key, [])
        return values

    def __setitem__(self, meta_key, value):
        if meta_key not in ['key', 'file']:
            self.fields(**{meta_key: value})

    def __delitem__(self, meta_key):
        self.fields(**{meta_key: []})

    def __contains__(self, meta_key):
        return meta_key in self.fields()

    def __iter__(self):
        for field in self.fields().keys():
            if not field.endswith('lastchanged'):
                yield field

    def __len__(self):
        len([x for x in self])

    def __repr__(self):
        repr_ = 'GitAnnexMetadata(key={!r}, path={!r})'
        return repr_.format(self.key, self.annex.repo.path)


class RepeatedProcess:
    def __init__(self, *prefix_command, workdir=None):
        self._prefix = prefix_command
        self._workdir = workdir

    def __call__(self, *commands):
        return subprocess.check_output(
            (*self._prefix, *commands),
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self._workdir,
        )

    def __repr__(self):
        repr_ = 'RepeatedProcess(prefix={!r}, workdir={!r})'
        return repr_.format(self._prefix, self._workdir)


class BatchProcess:
    def __init__(self, *batch_command, workdir=None):
        self._command = batch_command
        self._workdir = workdir
        self._process = self.start()

    def start(self):
        process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self._workdir,
        )
        return process

    def running(self):
        return self._process and self._process.poll() is None

    def terminate(self, kill=False):
        self._process.terminate()
        try:
            self._process.wait(5)
        except subprocess.TimeoutExpired:
            if kill:
                self._process.kill()
            else:
                raise

    def restart(self):
        if self.running():
            self.terminate()
        self._process = self.start()

    def __call__(self, *query_line, **query_object):
        while not self.running():
            self._process = self.start()

        query = " ".join(query_line) or json.dumps(query_object)
        print(query, file=self._process.stdin, flush=True)
        response = self._process.stdout.readline().strip()
        return response if query_line else json.loads(response)

    def __repr__(self):
        repr_ = 'BatchProcess(cmd={!r}, cwd={!r}, process={!r})'
        return repr_.format(self._command, self._workdir, self._process)


def files_in(dir_path, relative=False):
    exclude = ['.git']
    for root, dirs, files in os.walk(dir_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        if relative:
            root = os.path.relpath(root, start=relative)
        for f in files:
            yield os.path.join(root, f)
