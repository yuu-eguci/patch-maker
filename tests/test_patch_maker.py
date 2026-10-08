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
