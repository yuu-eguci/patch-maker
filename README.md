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

### Python で実行する

Python 3.13 以上が必要です。外部ライブラリは使いません。

```bash
python PatchMaker.py
```

### Docker で実行する

```bash
docker build -t patch-maker .
docker run --rm -v "$PWD:/app" patch-maker
```

## Development

テストと lint は Docker で実行できます。

```bash
docker build -t patch-maker .
docker run --rm patch-maker sh -c 'ruff check . && ruff format --check . && pytest -q'
```

ローカルでは Python 3.13 以上の環境へ `pip install pytest ruff` を実行したあと、 `pytest` と `ruff check .` で実行できます。

作業記録は [docs/iona-kest.md](docs/iona-kest.md) にあります。
