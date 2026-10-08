"""PatchMaker の特性テストです。"""

import io
import ntpath
import os
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
    monkeypatch.setattr('sys.stdin', io.StringIO('a.txt\r\nd/b.txt\r\n'))

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
    monkeypatch.setattr('sys.stdin', io.StringIO(''))

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
    assert '2 symlinks above were skipped' in out


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
    assert '16 symlinks above were skipped' in capsys.readouterr().out


def test_make_pathlist_decodes_git_quoted_paths():
    pm = PatchMaker.PatchMaker()
    lines = '"d/\\346\\227\\245.txt"\n"tab\\there.txt"\n"say \\"hi\\".txt"\n'

    assert pm.make_pathlist(lines) == ['d/日.txt', 'tab\there.txt', 'say "hi".txt']


@pytest.mark.parametrize('line', ['"unterminated', '"\\q"', '"\\777"', '"日.txt"', 'plain.txt'])
def test_make_pathlist_keeps_lines_that_are_not_git_quoted(line):
    assert PatchMaker.PatchMaker().make_pathlist([line]) == [line]


def test_main_copies_git_quoted_path_from_stdin(workdir, no_cd, monkeypatch):
    write(workdir / 'd/日.txt', 'jp')
    monkeypatch.setattr('sys.stdin', io.StringIO('"d/\\346\\227\\245.txt"\n'))

    assert PatchMaker.main(['-']) == 0
    assert (workdir / 'test_patch/d/日.txt').read_text() == 'jp'


def test_run_skips_broken_symlinks_in_directory(appdir, capsys):
    write(appdir / 'd/keep.txt', 'keep')
    (appdir / 'd/broken.txt').symlink_to('missing.txt')

    assert PatchMaker.PatchMaker().run(['d']) == 0

    assert (appdir / 'test_patch/d/keep.txt').read_text() == 'keep'
    assert not (appdir / 'test_patch/d/broken.txt').exists()
    assert '1 symlinks above were skipped' in capsys.readouterr().out
