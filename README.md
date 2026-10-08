PatchMaker
===

選択したファイルやディレクトリを、タイムスタンプ付きのパッチディレクトリ (`YYYYmmdd_HHMMSS_patch`) へ相対パスを保ったままコピーするツールです。

## Usage

![1](media/PATCHMAKER.jpg)

- git で変更されたファイルパス一覧を取得します。
- それを `PatchMaker.py` 冒頭の `targetpaths` 文字列へ貼り付けます。
- 実行します。パスは `PatchMaker.py` があるディレクトリからの相対パスとして扱います。
- パッチディレクトリが `PatchMaker.py` と同じディレクトリに作成されます。
- 存在しないパスは一覧表示され、コピーされません。

### パスの扱い

- 各行の前後の空白と改行コード (CRLF の `\r` を含みます) は取り除きます。空行は無視します。
- 絶対パス、ドライブ付きのパス (Windows の `C:foo` など) 、ディレクトリ全体 (`.`) 、 `..` で外を指すパスは拒否します。拒否したパスは一覧表示され、コピーされません。
- シンボリックリンクはリンク先の内容をコピーします。
- 同じパスを複数回指定しても 1 回だけコピーし、 1 回だけ報告します。
- ディレクトリとその配下のパスを同時に指定した場合は、ディレクトリだけをコピーします。
- コピーはパスの辞書順で行います。

### Python で実行する

Python 3.13 以上が必要です。外部ライブラリは使いません。

```bash
python PatchMaker.py
```

### Docker で実行する

```bash
docker build -t patch-maker .
docker run --rm -e TZ=Asia/Tokyo --user "$(id -u):$(id -g)" -v "$PWD:/app" patch-maker
```

- `-e TZ=Asia/Tokyo` を省くと、パッチ名の時刻はコンテナの UTC になります。
- `--user` を省くと、 Linux ではパッチディレクトリの所有者が root になります。

## Development

テストと lint は Docker で実行できます。

```bash
docker build -t patch-maker .
docker run --rm patch-maker sh -c 'ruff check . && ruff format --check . && pytest -q'
```

ローカルでは Python 3.13 以上の環境へ `pip install -r requirements-dev.txt` を実行したあと、 `pytest` と `ruff check .` で実行できます。開発用ライブラリのバージョンは `requirements-dev.txt` で固定しています。

GitHub Actions の CI (`.github/workflows/ci.yml`) でも同じ lint とテストを実行します。

作業記録は [docs/iona-kest.md](docs/iona-kest.md) にあります。
