import unittest
import os

from tests.utils import with_folder
from tests.utils import with_repo


class TestGitRepo(unittest.TestCase):
    @with_repo()
    def test_git(self, repo):
        repo._git('--version')

    @with_repo()
    def test_git_status(self, repo):
        assert not repo.status

    @with_repo()
    def test_git_commit(self, repo):
        repo.commit('Test commit', allow_empty=True)

    @with_repo('repo-tars/initial-commit.tar.gz')
    def test_git_from_tar_1(self, repo):
        assert repo.tree_hash == \
               '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

    @with_repo('repo-tars/empty.tar.gz')
    def test_git_from_tar_2(self, repo):
        assert repo.branches == ()

    @with_repo('repo-tars/three-branches-a.tar.gz')
    def test_git_branches_1(self, repo):
        assert repo.branches == \
               ('a', 'master', 'x')

    @with_repo('repo-tars/three-branches-m.tar.gz')
    def test_git_branches_2(self, repo):
        assert repo.branches == \
               ('master', 'a', 'x')

    @with_repo('repo-tars/three-branches-x.tar.gz')
    def test_git_branches_3(self, repo):
        assert repo.branches == \
               ('x', 'a', 'master')

    @with_repo('repo-tars/three-branches-m.tar.gz')
    def test_git_checkout(self, repo):
        assert repo.branches == \
               ('master', 'a', 'x')

        repo.checkout('a')
        assert repo.branches == \
               ('a', 'master', 'x')

        repo.checkout('x')
        assert repo.branches == \
               ('x', 'a', 'master')

        repo.checkout('n')
        assert repo.branches == \
               ('n', 'a', 'master', 'x')

    @with_repo('repo-tars/detached-head.tar.gz')
    def test_git_detached_head(self, repo):
        assert repo.branches == \
               ('(HEAD detached at ae034d5)', 'master')

    @with_repo('repo-tars/two-files-extend.tar.gz')
    def test_git_cherry_pick(self, repo):
        repo.checkout('895131e', new_branch=False)
        repo.checkout('alt')
        repo.cherry_pick('678ff80')
        assert repo.tree_hash == \
            '9af9706879aba9cbfc7e8f70e8fe87c20d6678db'

    @with_repo('repo-tars/two-half-files-extend.tar.gz')
    def test_git_stash(self, repo):
        assert repo.status
        repo.stash()
        assert not repo.status
        repo.checkout('master')
        repo.cherry_pick('e21989f')
        repo.stash(pop=True)
        repo.commit('extend file c')
        assert repo.tree_hash == \
            '149cb6cb6b7ffa7508ce5b4936f307de2acdbe17'

    @with_repo('repo-tars/two-files-extend.tar.gz')
    def test_git_move_free(self, repo):
        repo.move('b.txt', 'c.txt')
        repo.commit('move b to c')
        assert repo.tree_hash == \
            '433015e2412dce520e9117002d42f6b31a06a406'

    @with_repo('repo-tars/two-files-extend.tar.gz')
    def test_git_move_conflict(self, repo):
        repo.move('a.txt', 'b.txt', overwrite=True)
        repo.commit('move a to b')
        assert repo.tree_hash == \
               '83628542da01fb677c2afcb0e8c934023a56412e'


class TestGitAnnexRepo(unittest.TestCase):
    @with_repo(annex=True)
    def test_git(self, repo):
        repo.annex._annex('version')

    @with_repo('annex-tars/single-file.tar.gz', annex=True)
    def test_calckey(self, repo):
        key = 'SHA256E-s1000--' \
            'e109ee3a23b6f06d5d303d761c8937cf' \
            'b4320c27c14395260b0fc2e8afb5d761.txt'
        assert repo.annex.calckey('a.txt') == key

    @with_repo('annex-tars/single-file.tar.gz', annex=True)
    def test_locate(self, repo):
        key = 'SHA256E-s1000--' \
            'e109ee3a23b6f06d5d303d761c8937cf' \
            'b4320c27c14395260b0fc2e8afb5d761.txt'
        assert repo.annex.locate(key) == \
            '.git/annex/objects/q5/F4/{}/{}'.format(key, key)

    @with_repo('annex-tars/two-identical.tar.gz', annex=True)
    def test_git_move_same(self, repo):
        repo.move('a.txt', 'b.txt')
        repo.commit('move a to b')
        assert repo.tree_hash == \
            'bfbabae495c75f33ff22f262decf12d39ba79678'

    @with_repo(annex=True)
    @with_folder('data-tars/three-nested.tar.gz')
    def test_import(self, repo, temp_folder):
        tmp_name = os.path.basename(temp_folder)
        repo.annex.import_(temp_folder)
        repo.move(tmp_name, 'new')
        repo.commit('import files')
        assert repo.tree_hash == \
            '265633410b1db4d12458a27a3209a161880c8794'
        repo.annex.import_(temp_folder)
        repo.move(tmp_name, 'new')
        assert not repo.status

    @with_repo(annex=True)
    @with_folder('data-tars/three-nested.tar.gz')
    def test_import_conflict(self, repo, temp_folder):
        repo.annex.import_(temp_folder)
        with self.assertRaises(ValueError):
            repo.annex.import_(temp_folder)

    @with_repo('annex-tars/metadata-two.tar.gz', annex=True)
    def test_keys_files(self, repo):
        key_a = 'SHA256E-s1000--' \
            '9b5c838c2f22a5ab7f0a832dcae4be54' \
            'df2a6cc5856e6440da60265de8ded5a2.txt'

        key_b = 'SHA256E-s1000--' \
            '155b0b081f29291a46cd3ae8da1fc5f1' \
            '4e7bf96baef2a8a484c1e3833fd6fea2.txt'

        assert repo.annex.keys() == {key_a, key_b}
        assert repo.annex.files() == {'a.txt', 'b/b.txt'}


class TestGitAnnexMetadata(unittest.TestCase):
    @with_repo('annex-tars/metadata-two.tar.gz', annex=True)
    def test_mapping(self, repo):
        key_a = 'SHA256E-s1000--' \
                '9b5c838c2f22a5ab7f0a832dcae4be54' \
                'df2a6cc5856e6440da60265de8ded5a2.txt'
        meta_a = repo.annex[key_a]

        assert meta_a['test_str'] == ['OK']
        assert meta_a['test_int'] == ['3']
        assert set(meta_a['test_list']) == {'one', 'two', 'three'}

        del meta_a['test_int']
        assert 'test_int' not in meta_a

        meta_a['test'] = ['test']
        assert meta_a['test'] == ['test']

        meta_a['test_list'] += ['four']
        assert set(meta_a['test_list']) \
               == {'one', 'two', 'three', 'four'}

        meta_a['test_list'].remove('one')
        meta_a['test_list'].remove('two')
        meta_a['test_list'].remove('four')
        assert meta_a['test_list'] == ['three']

        key = 'SHA256E-s1000--' \
            '00000000000000000000000000000000' \
            '00000000000000000000000000000000.txt'
        with self.assertRaises(KeyError):
            m = repo.annex[key]

    @with_repo(annex=True)
    @with_folder(files=['annex-tars/single-file.tar.gz'])
    def test_repeat_condition(self, repo, temp_folder):
        repo.annex.import_(temp_folder)
        repo.commit('annex tar')
        key = repo.annex.keys().pop()

        meta = repo.annex[key]
        for val in ['a', 'b', 'c', 'd', 'e', 'a', 'b', 'c', 'd', 'e']:
            meta['test'] = [val]
            assert meta['test'] == [val]
