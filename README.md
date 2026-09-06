# chappy — Code for Handling Absorption Profiles with PYthon

**日本語** | [English](README.en.md)

[![CI](https://github.com/Di-Is/qso-chappy/actions/workflows/ci.yml/badge.svg)](https://github.com/Di-Is/qso-chappy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22162939.svg)](https://doi.org/10.5281/zenodo.22162939)

遠くのクェーサーから届いた光は、地球に着くまでに宇宙空間のガス雲をいくつも通り抜けてきます。
その途中で特定の波長だけが吸収され、スペクトルには「吸収線」という暗い筋が刻まれます。

chappy は、この吸収線のかたちを測ることで、光をさえぎったガスがどれだけの量で、
どんな速度と温度を持っていたのかを推定するデスクトップアプリケーションです。
天文学に強い興味を持つ小中学生から、市民科学者、研究で日常的に利用する学生・研究者まで、
幅広い利用者を想定しています。

## できること

- **スペクトルを見る** — FITS 形式の分光データを読み込み、拡大・移動しながら波長ごとの様子を確認できます
- **連続光を調整する** — 吸収線を測る基準となる連続光（コンティニュアム）を対話的に編集できます
- **吸収線を当てはめる** — Voigt プロファイルを重ねて、柱密度・速度分散・視線速度を推定します
- **自動で最適化する** — 手で置いた初期値から、当てはまりが最も良くなるパラメータを自動で探します
- **吸収線の正体を調べる** — 波長の並びから、どの元素・イオンによる吸収かを同定できます
- **結果を残す** — 解析をプロジェクトとして保存し、後から再開・共有・エクスポートできます

画面は日本語と英語を切り替えられます。

## はじめかた

1. [Releases](https://github.com/Di-Is/qso-chappy/releases) から最新版の zip ファイルを入手し、任意の場所に展開します
2. [INSTALL.md](INSTALL.md) の手順に従ってセットアップします

Python を自分でインストールする必要はありません。必要な Python と依存パッケージは初回起動時に自動で用意されます。

**初めて起動すると、チュートリアルが自動的に始まります。**
サンプルのクェーサースペクトルが同梱されているので、自分のデータを用意しなくてもすぐ試せます。

## 使い方を調べる

アプリの「ヘルプ > ユーザーガイド」から、画面ごとの操作説明を開けます。
マニュアルは配布パッケージに同梱されており、表示中の言語に合わせて日本語版・英語版が開きます。

## 動作環境

- Windows / macOS / Linux
- Python 3.12 以降

## 困ったときは

うまく動かないときや、使い方で迷ったときは、メーリングリスト [chappy-ml@shinshu-u.ac.jp](mailto:chappy-ml@shinshu-u.ac.jp) までお知らせください。
天文学やプログラミングの専門知識は必要ありません。「何をしようとして」「何が起きたか」を書いていただければ十分です。

GitHub を使い慣れている方は、バグ報告や機能要望を [Issues](https://github.com/Di-Is/qso-chappy/issues) に出していただいても構いません。

## 開発に参加する

バグ報告・機能提案・プルリクエストを歓迎します。
開発環境の構築やコーディング規約は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## ライセンス

MIT License — 研究・教育・改変・再配布のいずれにも自由にお使いいただけます。
詳細は [LICENSE](LICENSE) を参照してください。

同梱のサンプルスペクトル（`sample_data/`）のみ、出典元の条件により CC BY 4.0 が適用されます。
出典と帰属表示は [sample_data/README.md](sample_data/README.md) を参照してください。

## 引用

研究成果で chappy を利用した場合は、以下の DOI を引用してください。
このリンクは常に最新バージョンを指します。

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22162939.svg)](https://doi.org/10.5281/zenodo.22162939)

書誌情報は [CITATION.cff](CITATION.cff) にまとめてあります。
GitHub のリポジトリ右側「Cite this repository」から各種形式で取得できます。

## このプロジェクトについて

同梱のサンプルデータの出典と観測情報は [sample_data/README.md](sample_data/README.md) に記載しています。
