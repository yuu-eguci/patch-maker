"""PatchMaker の特性テストです。"""

import io
import ntpath
import os
import stat
from pathlib import PureWindowsPath

import pytest

import PatchMaker


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """一時ディレクトリへ移動し、固定のパッチ名を使います。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PatchMaker, 'PATCHNAME', 'test_patch')
    return tmp_path


def write(path, text='x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_make_pathlist_ignores_blank_lines():
    pm = PatchMaker.PatchMaker()
    assert pm.make_pathlist('\n\na/b.txt\n\nc.txt\n\n') == ['a/b.txt', 'c.txt']


def test_run_copies_files_preserving_relative_paths(workdir):
    write(workdir / 'project/html/html1.html', 'one')
    write(workdir / 'project/html/html2.html', 'two')

    PatchMaker.PatchMaker().run('project/html/html1.html\nproject/html/html2.html\n')

    assert (workdir / 'test_patch/project/html/html1.html').read_text() == 'one'
    assert (workdir / 'test_patch/project/html/html2.html').read_text() == 'two'


def test_run_copies_directories(workdir):
    write(workdir / 'd/sub/f.txt', 'f')

    PatchMaker.PatchMaker().run(['d'])

    assert (workdir / 'test_patch/d/sub/f.txt').read_text() == 'f'


def test_run_reports_missing_paths(workdir, capsys):
    write(workdir / 'a.txt')

    PatchMaker.PatchMaker().run(['a.txt', 'missing.txt'])

    out = capsys.readouterr().out
    assert "'missing.txt'" in out
    assert '1 files above were not found' in out
    assert os.path.exists(workdir / 'test_patch/a.txt')


def test_make_pathlist_strips_whitespace_and_crlf():
    pm = PatchMaker.PatchMaker()
    assert pm.make_pathlist('  a.txt  \r\n\tb.txt\r\n \r\n') == ['a.txt', 'b.txt']


def test_run_accepts_crlf_input(workdir):
    write(workdir / 'a.txt', 'a')

    PatchMaker.PatchMaker().run('a.txt\r\n')

    assert (workdir / 'test_patch/a.txt').read_text() == 'a'


@pytest.mark.parametrize('target', ['../outside.txt', 'd/../../outside.txt'])
def test_run_rejects_paths_escaping_patch_directory(tmp_path, monkeypatch, capsys, target):
    app = tmp_path / 'app'
    write(app / 'd/keep.txt')
    write(tmp_path / 'outside.txt', 'secret')
    monkeypatch.chdir(app)
    monkeypatch.setattr(PatchMaker, 'PATCHNAME', 'test_patch')

    PatchMaker.PatchMaker().run([target])

    assert not (app / 'outside.txt').exists()
    assert list((app / 'test_patch').rglob('*')) == []
    out = capsys.readouterr().out
    assert repr(target) in out
    assert '1 paths above were rejected' in out


def test_run_rejects_absolute_paths(workdir, capsys):
    target = workdir / 'a.txt'
    write(target)

    PatchMaker.PatchMaker().run([str(target)])

    assert list((workdir / 'test_patch').rglob('*')) == []
    assert '1 paths above were rejected' in capsys.readouterr().out


def test_run_copies_duplicated_paths_once(workdir, capsys):
    write(workdir / 'a.txt')

    PatchMaker.PatchMaker().run(['a.txt', 'a.txt', './a.txt'])

    assert (workdir / 'test_patch/a.txt').exists()
    assert '1 patch files were created' in capsys.readouterr().out


@pytest.mark.parametrize('targets', [['d', 'd/f.txt'], ['d/f.txt', 'd']])
def test_run_copies_directory_with_its_children_listed(workdir, targets):
    write(workdir / 'd/f.txt', 'f')
    write(workdir / 'd/g.txt', 'g')

    PatchMaker.PatchMaker().run(targets)

    assert (workdir / 'test_patch/d/f.txt').read_text() == 'f'
    assert (workdir / 'test_patch/d/g.txt').read_text() == 'g'


def test_create_patch_copies_in_sorted_order(workdir):
    for name in ['c.txt', 'a.txt', 'b.txt']:
        write(workdir / name)

    donelist = PatchMaker.PatchMaker().create_patch(['c.txt', 'a.txt', 'b.txt'])

    assert donelist == ['test_patch/a.txt', 'test_patch/b.txt', 'test_patch/c.txt']


@pytest.mark.parametrize('target', ['.', './', 'a/..'])
def test_run_rejects_whole_directory(workdir, capsys, target):
    write(workdir / 'a/f.txt')

    PatchMaker.PatchMaker().run([target])

    assert list((workdir / 'test_patch').rglob('*')) == []
    assert '1 paths above were rejected' in capsys.readouterr().out


@pytest.mark.parametrize('target', ['\\foo', '/foo', 'C:foo', 'C:\\foo', 'C:..\\x', '..\\x'])
def test_is_unsafe_path_rejects_windows_rooted_paths(monkeypatch, target):
    monkeypatch.setattr(PatchMaker.os, 'path', ntpath)
    monkeypatch.setattr(PatchMaker, 'PurePath', PureWindowsPath)

    assert PatchMaker.PatchMaker().is_unsafe_path(target)


@pytest.mark.parametrize('targets', [['d/', 'd/f.txt'], ['d/./f.txt', 'd/f.txt']])
def test_run_normalizes_trailing_slash_and_dot_segments(workdir, capsys, targets):
    write(workdir / 'd/f.txt', 'f')

    PatchMaker.PatchMaker().run(targets)

    assert (workdir / 'test_patch/d/f.txt').read_text() == 'f'
    assert '1 patch files were created' in capsys.readouterr().out


def test_run_reports_duplicated_missing_path_once(workdir, capsys):
    PatchMaker.PatchMaker().run(['missing.txt', 'missing.txt'])

    assert '1 files above were not found' in capsys.readouterr().out


def fake_stdin(monkeypatch, data: bytes, encoding='cp932'):
    """OS の文字コードが UTF-8 以外の環境を想定した標準入力に差し替えます。"""
    monkeypatch.setattr('sys.stdin', io.TextIOWrapper(io.BytesIO(data), encoding=encoding))


@pytest.fixture
def no_cd(monkeypatch):
    """main() がスクリプトのディレクトリへ移動しないようにします。"""
    monkeypatch.setattr(PatchMaker.PatchMaker, 'cd_', lambda self: None)


def test_main_uses_targetpaths_without_arguments(workdir, no_cd, monkeypatch):
    write(workdir / 'a.txt', 'a')
    monkeypatch.setattr(PatchMaker, 'targetpaths', '\na.txt\n')

    PatchMaker.main([])

    assert (workdir / 'test_patch/a.txt').read_text() == 'a'


def test_main_uses_command_line_arguments(workdir, no_cd):
    write(workdir / 'a.txt', 'a')
    write(workdir / 'b.txt', 'b')

    PatchMaker.main(['a.txt'])

    assert (workdir / 'test_patch/a.txt').exists()
    assert not (workdir / 'test_patch/b.txt').exists()


def test_main_reads_paths_from_stdin_with_dash(workdir, no_cd, monkeypatch):
    write(workdir / 'a.txt', 'a')
    write(workdir / 'd/b.txt', 'b')
    fake_stdin(monkeypatch, b'a.txt\r\nd/b.txt\r\n')

    PatchMaker.main(['-'])

    assert (workdir / 'test_patch/a.txt').read_text() == 'a'
    assert (workdir / 'test_patch/d/b.txt').read_text() == 'b'


def test_create_patch_adds_suffix_when_patch_directory_exists(workdir):
    write(workdir / 'a.txt', 'new')
    write(workdir / 'test_patch/a.txt', 'old')
    write(workdir / 'test_patch_2/a.txt', 'old')

    donelist = PatchMaker.PatchMaker().create_patch(['a.txt'])

    assert donelist == [os.path.join('test_patch_3', 'a.txt')]
    assert (workdir / 'test_patch/a.txt').read_text() == 'old'
    assert (workdir / 'test_patch_3/a.txt').read_text() == 'new'


def test_run_prints_patch_directory_name(workdir, capsys):
    write(workdir / 'a.txt')

    PatchMaker.PatchMaker().run(['a.txt'])

    assert '<INFO> Patch directory: test_patch' in capsys.readouterr().out


@pytest.mark.parametrize('argv', [['missing.txt'], ['../outside.txt']])
def test_main_fails_without_creating_patch_when_nothing_to_copy(workdir, no_cd, capsys, argv):
    assert PatchMaker.main(argv) == 1

    assert not (workdir / 'test_patch').exists()
    captured = capsys.readouterr()
    assert 'No files to copy' in captured.err
    assert 'Succeeded' not in captured.out


def test_main_fails_with_empty_stdin(workdir, no_cd, monkeypatch):
    fake_stdin(monkeypatch, b'')

    assert PatchMaker.main(['-']) == 1
    assert not (workdir / 'test_patch').exists()


def test_main_returns_zero_on_success(workdir, no_cd):
    write(workdir / 'a.txt')

    assert PatchMaker.main(['a.txt']) == 0


@pytest.fixture
def appdir(tmp_path, monkeypatch):
    """外側にファイルを置いた app ディレクトリへ移動します。"""
    app = tmp_path / 'app'
    app.mkdir()
    write(tmp_path / 'outside/secret.txt', 'secret')
    monkeypatch.chdir(app)
    monkeypatch.setattr(PatchMaker, 'PATCHNAME', 'test_patch')
    return app


@pytest.mark.parametrize('target', ['link.txt', 'linkdir/secret.txt'])
def test_run_rejects_symlink_resolving_outside(appdir, capsys, target):
    (appdir / 'link.txt').symlink_to(appdir.parent / 'outside/secret.txt')
    (appdir / 'linkdir').symlink_to(appdir.parent / 'outside')

    assert PatchMaker.PatchMaker().run([target]) == 1

    assert '1 paths above were rejected' in capsys.readouterr().out


def test_run_skips_links_in_directory_pointing_outside(appdir, capsys):
    write(appdir / 'd/keep.txt', 'keep')
    (appdir / 'd/secret.txt').symlink_to(appdir.parent / 'outside/secret.txt')
    (appdir / 'd/outside').symlink_to(appdir.parent / 'outside')

    PatchMaker.PatchMaker().run(['d'])

    assert (appdir / 'test_patch/d/keep.txt').read_text() == 'keep'
    assert not (appdir / 'test_patch/d/secret.txt').exists()
    assert not (appdir / 'test_patch/d/outside').exists()
    out = capsys.readouterr().out
    assert '2 entries above were skipped' in out


def test_run_skips_symlink_loops(appdir):
    write(appdir / 'project/a/f.txt', 'a')
    write(appdir / 'project/b/g.txt', 'b')
    (appdir / 'project/a/up').symlink_to('..')
    (appdir / 'project/a/to_b').symlink_to('../b')
    (appdir / 'project/b/to_a').symlink_to('../a')

    PatchMaker.PatchMaker().run(['project/a'])

    assert (appdir / 'test_patch/project/a/f.txt').read_text() == 'a'
    assert (appdir / 'test_patch/project/a/to_b/g.txt').read_text() == 'b'
    assert not (appdir / 'test_patch/project/a/up').exists()
    assert not (appdir / 'test_patch/project/a/to_b/to_a').exists()


def test_run_follows_symlinks_inside_directory(appdir):
    write(appdir / 'real.txt', 'real')
    write(appdir / 'd/keep.txt')
    (appdir / 'd/link.txt').symlink_to('../real.txt')

    PatchMaker.PatchMaker().run(['d'])

    copied = appdir / 'test_patch/d/link.txt'
    assert not copied.is_symlink()
    assert copied.read_text() == 'real'


def test_run_checks_normalized_path_for_symlinks(appdir):
    write(appdir / 'deep/foo', 'inside')
    (appdir / 'linkdir').symlink_to(appdir / 'deep/x', target_is_directory=True)
    (appdir / 'deep/x').mkdir()
    (appdir / 'foo').symlink_to(appdir.parent / 'outside/secret.txt')

    assert PatchMaker.PatchMaker().run(['linkdir/../foo']) == 1

    assert not (appdir / 'test_patch/foo').exists()


def test_run_copies_directory_reached_by_several_links_once(appdir, capsys):
    for i in range(16):
        (appdir / f'chain/d{i}').mkdir(parents=True)
    write(appdir / 'chain/d16/f.txt', 'f')
    for i in range(16):
        (appdir / f'chain/d{i}/x').symlink_to(f'../d{i + 1}')
        (appdir / f'chain/d{i}/y').symlink_to(f'../d{i + 1}')

    PatchMaker.PatchMaker().run(['chain/d0'])

    copied = list((appdir / 'test_patch').rglob('f.txt'))
    assert len(copied) == 1
    assert '16 entries above were skipped' in capsys.readouterr().out


def test_make_pathlist_decodes_git_quoted_paths():
    pm = PatchMaker.PatchMaker()
    lines = '"d/\\346\\227\\245.txt"\n"tab\\there.txt"\n"say \\"hi\\".txt"\n'

    assert pm.make_pathlist(lines) == ['d/日.txt', 'tab\there.txt', 'say "hi".txt']


@pytest.mark.parametrize('line', ['"unterminated', '"\\q"', '"\\777"', '"日.txt"', 'plain.txt'])
def test_make_pathlist_keeps_lines_that_are_not_git_quoted(line):
    assert PatchMaker.PatchMaker().make_pathlist([line]) == [line]


def test_main_copies_git_quoted_path_from_stdin(workdir, no_cd, monkeypatch):
    write(workdir / 'd/日.txt', 'jp')
    fake_stdin(monkeypatch, b'"d/\\346\\227\\245.txt"\n')

    assert PatchMaker.main(['-']) == 0
    assert (workdir / 'test_patch/d/日.txt').read_text() == 'jp'


def test_run_skips_broken_symlinks_in_directory(appdir, capsys):
    write(appdir / 'd/keep.txt', 'keep')
    (appdir / 'd/broken.txt').symlink_to('missing.txt')

    assert PatchMaker.PatchMaker().run(['d']) == 0

    assert (appdir / 'test_patch/d/keep.txt').read_text() == 'keep'
    assert not (appdir / 'test_patch/d/broken.txt').exists()
    assert '1 entries above were skipped' in capsys.readouterr().out


def test_make_pathlist_keeps_git_quoted_line_that_is_not_utf8():
    assert PatchMaker.PatchMaker().make_pathlist(['"\\377.txt"']) == ['"\\377.txt"']


def test_cd_moves_to_script_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    PatchMaker.PatchMaker().cd_()

    assert os.getcwd() == os.path.dirname(os.path.abspath(PatchMaker.__file__))


def test_run_reports_duplicated_rejected_path_once(workdir, capsys):
    PatchMaker.PatchMaker().run(['../x', '../x'])

    assert '1 paths above were rejected' in capsys.readouterr().out


@pytest.mark.parametrize('option', ['-h', '--help'])
def test_main_prints_usage_with_help_option(workdir, no_cd, capsys, option):
    assert PatchMaker.main([option]) == 0

    assert 'Usage:' in capsys.readouterr().out
    assert not (workdir / 'test_patch').exists()


def test_run_removes_partial_patch_when_copy_fails(workdir, capsys, monkeypatch):
    write(workdir / 'a.txt')
    write(workdir / 'b.txt')
    copyfile = PatchMaker.shutil.copyfile

    def fail_on_b(src, dst):
        if src == 'b.txt':
            raise PermissionError(13, 'Permission denied', src)
        return copyfile(src, dst)

    monkeypatch.setattr(PatchMaker.shutil, 'copyfile', fail_on_b)

    assert PatchMaker.PatchMaker().run(['a.txt', 'b.txt']) == 1

    assert not (workdir / 'test_patch').exists()
    captured = capsys.readouterr()
    assert 'Copy failed' in captured.err
    assert 'Succeeded' not in captured.out


def test_run_copies_directory_and_child_with_different_case(workdir):
    write(workdir / 'd/f.txt', 'a')
    if not (workdir / 'D').exists():
        pytest.skip('case-sensitive file system')

    assert PatchMaker.PatchMaker().run(['D/f.txt', 'd']) == 0

    assert (workdir / 'test_patch/d/f.txt').read_text() == 'a'


def test_run_prints_each_failed_path_when_copytree_fails(workdir, capsys, monkeypatch):
    write(workdir / 'd/x.txt')

    def fail(src, dst, **kwargs):
        raise PatchMaker.shutil.Error([('d/x.txt', 'test_patch/d/x.txt', '[Errno 13] Permission denied')])

    monkeypatch.setattr(PatchMaker.shutil, 'copytree', fail)

    assert PatchMaker.PatchMaker().run(['d']) == 1

    err = capsys.readouterr().err
    assert 'd/x.txt: [Errno 13] Permission denied' in err
    assert "[('" not in err


def test_run_reports_partial_patch_that_could_not_be_removed(workdir, capsys, monkeypatch):
    write(workdir / 'a.txt')

    def fail(src, dst):
        raise PermissionError(13, 'Permission denied', src)

    monkeypatch.setattr(PatchMaker.shutil, 'copyfile', fail)
    monkeypatch.setattr(PatchMaker.shutil, 'rmtree', lambda path, onexc: None)

    assert PatchMaker.PatchMaker().run(['a.txt']) == 1

    err = capsys.readouterr().err
    assert 'The partial patch directory remains: test_patch' in err
    assert 'was not created' not in err


@pytest.mark.skipif(os.name != 'posix' or os.geteuid() == 0, reason='root ignores permissions')
def test_run_removes_partial_patch_with_read_only_copies(workdir, monkeypatch):
    write(workdir / 'ro/f.txt')
    write(workdir / 'z.txt')
    (workdir / 'ro').chmod(0o555)
    copyfile = PatchMaker.shutil.copyfile

    def fail_on_z(src, dst):
        if src == 'z.txt':
            raise PermissionError(13, 'Permission denied', src)
        return copyfile(src, dst)

    monkeypatch.setattr(PatchMaker.shutil, 'copyfile', fail_on_z)

    try:
        assert PatchMaker.PatchMaker().run(['ro', 'z.txt']) == 1
        assert not (workdir / 'test_patch').exists()
    finally:
        (workdir / 'ro').chmod(0o755)
        if (workdir / 'test_patch/ro').exists():
            (workdir / 'test_patch/ro').chmod(0o755)


def test_retry_with_write_permission_does_not_chmod_outside_patch(workdir):
    (workdir / 'test_patch').mkdir()
    workdir.chmod(0o755)
    pm = PatchMaker.PatchMaker()
    pm.patchdir = 'test_patch'

    pm.retry_with_write_permission(lambda path: None, 'test_patch', None)

    assert workdir.stat().st_mode & 0o777 == 0o755


def test_main_reads_stdin_as_utf8_with_bom(workdir, no_cd, monkeypatch):
    write(workdir / 'a.txt', 'a')
    write(workdir / 'd/日本.txt', 'jp')
    fake_stdin(monkeypatch, '\ufeffa.txt\nd/日本.txt\n'.encode())

    assert PatchMaker.main(['-']) == 0

    assert (workdir / 'test_patch/a.txt').read_text() == 'a'
    assert (workdir / 'test_patch/d/日本.txt').read_text() == 'jp'


def test_main_reads_non_utf8_stdin_without_crashing(workdir, no_cd, monkeypatch):
    name = os.fsdecode(b'\x93\xfa.txt')
    try:
        write(workdir / name, 'sjis')
    except (OSError, UnicodeEncodeError):
        pytest.skip('file system rejects non UTF-8 names')
    fake_stdin(monkeypatch, b'\x93\xfa.txt\n')

    assert PatchMaker.main(['-']) == 0

    assert (workdir / 'test_patch' / name).read_text() == 'sjis'


@pytest.mark.parametrize('target', ['.git/config', 'sub/.git', 'sub/.GIT/HEAD'])
def test_run_rejects_paths_containing_git_directory(workdir, capsys, target):
    write(workdir / target)

    assert PatchMaker.PatchMaker().run([target]) == 1

    assert '1 paths above were rejected' in capsys.readouterr().out


def test_run_skips_git_entries_inside_directory(workdir, capsys):
    write(workdir / 'vendor/lib/f.txt', 'f')
    write(workdir / 'vendor/lib/.git', 'gitdir: ../../.git/modules/vendor/lib')
    write(workdir / 'vendor/lib/sub/.git/config')

    assert PatchMaker.PatchMaker().run(['vendor']) == 0

    assert (workdir / 'test_patch/vendor/lib/f.txt').read_text() == 'f'
    assert not (workdir / 'test_patch/vendor/lib/.git').exists()
    assert not (workdir / 'test_patch/vendor/lib/sub/.git').exists()
    out = capsys.readouterr().out
    assert '2 entries above were skipped' in out


@pytest.mark.parametrize('target', ['d', 'd/f'])
def test_run_drops_special_permission_bits(workdir, target):
    write(workdir / 'd/f')
    (workdir / 'd/f').chmod(0o6755)
    if stat.S_IMODE((workdir / 'd/f').stat().st_mode) != 0o6755:
        pytest.skip('file system ignores special bits')

    assert PatchMaker.PatchMaker().run([target]) == 0

    assert stat.S_IMODE((workdir / 'test_patch/d/f').stat().st_mode) == 0o755


def test_run_rejects_path_with_nul_character(workdir, capsys):
    assert PatchMaker.PatchMaker().run(['a\x00b']) == 1

    assert '1 paths above were rejected' in capsys.readouterr().out


@pytest.mark.parametrize('target', ['gl', 'gl/config', 'cfg', '.git.', 'sub/.git /x'])
def test_run_rejects_paths_resolving_into_git(workdir, capsys, target):
    write(workdir / '.git/config', 'secret')
    (workdir / 'gl').symlink_to('.git')
    (workdir / 'cfg').symlink_to('.git/config')

    assert PatchMaker.PatchMaker().run([target]) == 1

    assert '1 paths above were rejected' in capsys.readouterr().out


def test_run_skips_links_into_git_inside_directory(workdir, capsys):
    write(workdir / '.git/config', 'secret')
    write(workdir / 'd/f.txt', 'f')
    (workdir / 'd/gl').symlink_to('../.git')
    (workdir / 'd/cfg').symlink_to('../.git/config')

    assert PatchMaker.PatchMaker().run(['d']) == 0

    assert (workdir / 'test_patch/d/f.txt').read_text() == 'f'
    assert not (workdir / 'test_patch/d/gl').exists()
    assert not (workdir / 'test_patch/d/cfg').exists()
    assert '2 entries above were skipped' in capsys.readouterr().out


@pytest.mark.skipif(not hasattr(os, 'chflags') or not hasattr(stat, 'UF_IMMUTABLE'), reason='no file flags')
def test_run_copies_locked_file_without_flags(workdir):
    write(workdir / 'locked.txt', 'x')
    try:
        os.chflags(workdir / 'locked.txt', stat.UF_IMMUTABLE)
    except OSError:
        pytest.skip('file system rejects flags')
    try:
        assert PatchMaker.PatchMaker().run(['locked.txt']) == 0
        assert (workdir / 'test_patch/locked.txt').read_text() == 'x'
        assert not os.stat(workdir / 'test_patch/locked.txt').st_flags & stat.UF_IMMUTABLE
    finally:
        os.chflags(workdir / 'locked.txt', 0)
        if (workdir / 'test_patch/locked.txt').exists():
            os.chflags(workdir / 'test_patch/locked.txt', 0)


def test_run_drops_special_bits_of_directories(workdir):
    write(workdir / 'd/sub/f')
    (workdir / 'd/sub').chmod(0o3755)
    if stat.S_IMODE((workdir / 'd/sub').stat().st_mode) != 0o3755:
        pytest.skip('file system ignores special bits')

    assert PatchMaker.PatchMaker().run(['d']) == 0

    assert stat.S_IMODE((workdir / 'test_patch/d/sub').stat().st_mode) == 0o755


@pytest.mark.skipif(not hasattr(os, 'chflags') or not hasattr(stat, 'UF_IMMUTABLE'), reason='no file flags')
@pytest.mark.parametrize('fail', [False, True])
def test_run_handles_locked_directory(workdir, monkeypatch, fail):
    write(workdir / 'ad/f.txt', 'f')
    write(workdir / 'z.txt')
    try:
        os.chflags(workdir / 'ad', stat.UF_IMMUTABLE)
    except OSError:
        pytest.skip('file system rejects flags')
    copyfile = PatchMaker.shutil.copyfile

    def fail_on_z(src, dst):
        if fail and src == 'z.txt':
            raise PermissionError(13, 'Permission denied', src)
        return copyfile(src, dst)

    monkeypatch.setattr(PatchMaker.shutil, 'copyfile', fail_on_z)
    try:
        assert PatchMaker.PatchMaker().run(['ad', 'z.txt']) == (1 if fail else 0)
        if fail:
            assert not (workdir / 'test_patch').exists()
        else:
            assert not os.stat(workdir / 'test_patch/ad').st_flags & stat.UF_IMMUTABLE
    finally:
        os.chflags(workdir / 'ad', 0)
        if (workdir / 'test_patch/ad').exists():
            os.chflags(workdir / 'test_patch/ad', 0)
