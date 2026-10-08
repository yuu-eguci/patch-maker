"""PatchMaker の特性テストです。"""

import os

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
