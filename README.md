PatchMaker
===

パッチファイルを作成するツール。

- Docker: 対応!
- Python: 3.13!
- Linter: Ruff!
- Test: pytest!

## パッと実行してみたい

```bash
mkdir -p project/html && echo one > project/html/html1.html && echo two > project/html/html2.html
docker build -t patch-maker .
docker run --rm -e TZ=Asia/Tokyo --user "$(id -u):$(id -g)" -v "$PWD:/app" patch-maker
```

`YYYYmmdd_HHMMSS_patch/project/html/` に 2 ファイルがコピーされます。

## Usage

こうやる。

![1](media/PATCHMAKER.jpg)

- gitで変更されたファイルパス一覧を得る。
- それを丸コピーして targetpaths 文字列に貼る。
- 実行する。
- パッチファイルができる。
