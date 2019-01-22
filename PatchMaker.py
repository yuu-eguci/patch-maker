# coding: utf-8
# python3.6

'''PatchMaker

パッチファイルを作成するツール。
型注釈を使っているからpython3.6未満では動かない気がする。
'''

targetpaths = '''

project/html/html1.html
project/html/html2.html

'''

import os
import sys
from pprint import pprint
import datetime
import shutil


PATCHNAME = datetime.datetime.today().strftime('%Y%m%d_%H%M%S') + '_patch'


class PatchMaker:
    def __init__(self):
        pass

    def cd_(self):
        '''カレントディレクトリを移す。'''
        if hasattr(sys, 'frozen'):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))

    def run(self, targetpaths):
        '''トップレベルメソッド。'''
        # リストで渡しても文字列で渡してもいいようにしました。
        targetpaths = targetpaths if isinstance(targetpaths, list) else self.make_pathlist(targetpaths)
        absentpaths = self.get_absent_paths(targetpaths)
        donelist = self.create_patch(list(set(targetpaths)-set(absentpaths)))
        self.output_result(donelist, absentpaths)

    def make_pathlist(self, targetpaths: str) -> list:
        '''冒頭でインプットした文字列を配列にする。'''
        pathlist = []
        for t in targetpaths.strip().split('\n'):
            if t:
                pathlist.append(t)
        return pathlist

    def get_absent_paths(self, pathlist: list) -> list:
        '''インプットされたパスのうち、存在しないものを返します。'''
        return [path for path in pathlist if not os.path.exists(path)]

    def create_patch(self, pathlist: list) -> list:
        '''目的であるパッチの作成。'''
        os.mkdir(PATCHNAME)
        donelist = []
        for path in pathlist:
            dest_dir = f'{PATCHNAME}/{os.path.dirname(path)}'
            dest_file = f'{PATCHNAME}/{path}'
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            donelist.append(
                shutil.copytree(path, dest_file) 
                if os.path.isdir(path)
                else shutil.copy(path, dest_file))
        return donelist

    def output_result(self, donelist, absentpaths):
        '''「終わったよー」の出力。'''
        pprint(absentpaths)
        print(f'<INFO> {len(absentpaths)} files above were not found and were ignored.')
        print(f'<INFO> Succeeded! {len(donelist)} patch files were created. They are not shown on console.')


if __name__ == '__main__':
    pm = PatchMaker()
    pm.cd_()
    pm.run(targetpaths)
