"""PatchMaker

パッチファイルを作成するツールです。 Python 3.13 以上で動作します。
"""

targetpaths = """

project/html/html1.html
project/html/html2.html

"""

import ast
import datetime
import os
import re
import shutil
import sys
from pathlib import PurePath
from pprint import pprint

GIT_QUOTED_PATH = re.compile(r'"(?:[^"\\\x00-\x1f\x7f-\U0010ffff]|\\[abtnvfr"\\]|\\[0-3][0-7]{2})*"')

PATCHNAME = datetime.datetime.today().strftime('%Y%m%d_%H%M%S') + '_patch'


class PatchMaker:
    def cd_(self):
        """カレントディレクトリを移す。"""
        if hasattr(sys, 'frozen'):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))

    def run(self, targetpaths) -> int:
        """トップレベルメソッド。終了コードを返します。"""
        pathlist = self.make_pathlist(targetpaths)
        rejectedpaths = [path for path in pathlist if self.is_unsafe_path(path)]
        safepaths = [path for path in pathlist if path not in rejectedpaths]
        absentpaths = self.get_absent_paths(safepaths)
        copypaths = [path for path in safepaths if path not in absentpaths]
        self.output_ignored(absentpaths, rejectedpaths)
        if not copypaths:
            print('<ERROR> No files to copy. The patch directory was not created.', file=sys.stderr)
            return 1
        self.output_result(self.create_patch(copypaths))
        return 0

    def make_pathlist(self, targetpaths: str | list) -> list:
        """文字列またはリストで渡されたパスから、前後の空白と空行と重複を除いた配列を作ります。"""
        lines = targetpaths.splitlines() if isinstance(targetpaths, str) else targetpaths
        return list(dict.fromkeys(self.unquote_git_path(line.strip()) for line in lines if line.strip()))

    def unquote_git_path(self, line: str) -> str:
        """git が "d/\\346..." の形式で出力したパスを元のファイル名へ戻します。それ以外の行はそのまま返します。"""
        if not GIT_QUOTED_PATH.fullmatch(line):
            return line
        try:
            return ast.literal_eval('b' + line).decode()
        except UnicodeDecodeError:
            return line

    def is_unsafe_path(self, path: str) -> bool:
        """ルートやドライブ付きのパスと、ディレクトリ全体またはその外を指すパス (リンクは実体) を判定します。"""
        normalized = PurePath(os.path.normpath(path))
        return (
            bool(normalized.anchor)
            or normalized.parts[:1] in ((), ('..',))
            or not self.is_inside_base(os.path.normpath(path))
        )

    def is_inside_base(self, path: str) -> bool:
        """リンクを解決した実体が、カレントディレクトリの配下にあるかを判定します。"""
        return os.path.realpath(path).startswith(os.path.realpath(os.curdir) + os.sep)

    def get_absent_paths(self, pathlist: list) -> list:
        """インプットされたパスのうち、存在しないものを返します。"""
        return [path for path in pathlist if not os.path.exists(os.path.normpath(path))]

    def create_patch(self, pathlist: list) -> list:
        """目的であるパッチの作成。"""
        self.patchdir = self.make_patch_dir()
        self.skippedlinks = []
        donelist = []
        for path in self.select_copy_targets(pathlist):
            self.visited = set()
            dest = os.path.join(self.patchdir, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            donelist.append(
                shutil.copytree(path, dest, ignore=self.ignore_unsafe_links)
                if os.path.isdir(path)
                else shutil.copy(path, dest)
            )
        return donelist

    def ignore_unsafe_links(self, src: str, names: list) -> list:
        """copytree 中に、外側を指すリンクと、コピー済みのディレクトリや祖先を指すリンクを除外します。"""
        current = src
        while current not in ('', os.curdir):
            self.visited.add(os.path.realpath(current))
            current = os.path.dirname(current)
        ignored = []
        for name in names:
            path = os.path.join(src, name)
            if not (os.path.islink(path) or os.path.isjunction(path)):
                continue
            if not self.is_inside_base(path) or os.path.realpath(path) in self.visited:
                ignored.append(name)
                self.skippedlinks.append(path)
            elif os.path.isdir(path):
                self.visited.add(os.path.realpath(path))
        return ignored

    def make_patch_dir(self) -> str:
        """パッチディレクトリを作成して名前を返します。同名のディレクトリがあれば連番を付けます。"""
        patchdir, number = PATCHNAME, 1
        while True:
            try:
                os.mkdir(patchdir)
                return patchdir
            except FileExistsError:
                number += 1
                patchdir = f'{PATCHNAME}_{number}'

    def select_copy_targets(self, pathlist: list) -> list:
        """重複と、コピー対象ディレクトリの配下にあるパスを除き、辞書順に並べます。"""
        selected = []
        for path in sorted({os.path.normpath(path) for path in pathlist}):
            if not any(path.startswith(parent + os.sep) for parent in selected):
                selected.append(path)
        return selected

    def output_ignored(self, absentpaths, rejectedpaths):
        """コピーしなかったパスの出力。"""
        if rejectedpaths:
            pprint(rejectedpaths)
            print(f'<INFO> {len(rejectedpaths)} paths above were rejected because they are not inside this directory.')
        pprint(absentpaths)
        print(f'<INFO> {len(absentpaths)} files above were not found and were ignored.')

    def output_result(self, donelist):
        """「終わったよー」の出力。"""
        if self.skippedlinks:
            pprint(self.skippedlinks)
            print(f'<INFO> {len(self.skippedlinks)} symlinks above were skipped (outside or already copied).')
        print(f'<INFO> Succeeded! {len(donelist)} patch files were created. They are not shown on console.')
        print(f'<INFO> Patch directory: {self.patchdir}')


def main(argv: list | None = None) -> int:
    """引数があれば引数を、 `-` だけなら標準入力を、なければ冒頭の targetpaths を対象にします。"""
    argv = sys.argv[1:] if argv is None else argv
    paths = sys.stdin.read() if argv == ['-'] else argv or targetpaths
    pm = PatchMaker()
    pm.cd_()
    return pm.run(paths)


if __name__ == '__main__':
    sys.exit(main())
