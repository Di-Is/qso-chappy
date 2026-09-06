# CSVスキーマ概要

このリポジトリのツールが生成する代表的なCSV出力について、列構成と値の意味をまとめる。
対象は `src/spectral_database/cli.py` が吐き出す吸収線データベースCSV。

## `nist_lines.csv`（CLI出力）

### ファイル構造

- 先頭に任意のメタデータコメント行 `# name: ...` と `# version: ...` が付与される（`--meta-name`/`--meta-version`で制御）。
- 本文はカンマ区切り、UTF-8、ヘッダー1行＋データ本体で構成される（`csv_writer.write_csv`）。
- 行順は `absorption_multiplet_id` → 波長昇順でソートされる。

### 列定義

| 列名 | 型/フォーマット | 必須 | 説明 |
| --- | --- | --- | --- |
| line_id | 16文字の16進文字列 | ✓ | 遷移を正規化した文字列を`sha256`でハッシュした安定ID（`identifiers.hashed_line_id`）。 |
| name | 文字列 | ✓ | 遷移ラベル。NIST の原文ラベルを優先し、合成した水素系列線では `Lyα` や `Hα` などシリーズ名を自動生成。下位準位が基底項の微細構造励起準位である場合は末尾にアスタリスクを付す（例 `Si II 1194.5*`、`O I 1306.0**`）。 |
| element_symbol | 文字列 | ✓ | 元素記号。 |
| charge_state | 整数 | ✓ | 電離度（0=I, 1=II, ...）。 |
| wavelength | 小数（Å, vacuum） | ✓ | 最小不確かさを持つ波長値。 |
| wavelength_source | 文字列 | ✓ | 波長の出典。`ritz`（リッツ波長）、`observed`（観測値）、`aggregated`（水素系列線を (gf) 加重平均で合成した場合）を想定。 |
| wavelength_ritz | 小数（Å） | ✓ | リッツ波長。 |
| f_value | 小数（無次元, 科学表記） | ✓ | 吸収振動子強度。フォーマットは指数表記（`{:.6g}`）。 |
| gamma | 小数（s⁻¹, 科学表記） | ✓ | 自然幅 (\\Gamma)。同一上位準位からの全遷移の Einstein A 係数を合計し、必要に応じて下位準位の寄与も加算した放射減衰率。フォーマットは指数表記（`{:.6g}`）。 |
| wavelength_ritz_unc | 小数（Å） | | リッツ波長の不確かさ。 |
| wavelength_observed | 小数（Å） | | 観測波長（真空基準）。 |
| wavelength_observed_unc | 小数（Å） | | 観測波長の不確かさ。 |
| Ei_eV | 小数（eV） | | 下位準位エネルギー。 |
| Ek_eV | 小数（eV） | | 上位準位エネルギー。 |
| lower_conf | 文字列 | | 下位準位の電子配置。水素系列合成線では主量子数のみ（例 `2`）。 |
| lower_term | 文字列 | | 下位準位のLS項。水素系列合成線では空欄となる。 |
| lower_J | 文字列 | | 下位準位のJ量子数（整数または分数文字列）。水素系列合成線では空欄となる。 |
| upper_conf | 文字列 | | 上位準位の電子配置。水素系列合成線では主量子数のみ（例 `3`）。 |
| upper_term | 文字列 | | 上位準位のLS項。水素系列合成線では空欄となる。 |
| upper_J | 文字列 | | 上位準位のJ量子数。水素系列合成線では空欄となる。 |
| upper_term_LS | 文字列 | | 上位準位のLS項を正規化しパリティ記号を除いたもの。 |
| accuracy | 文字列 | | NIST精度コード。水素系列合成線では構成線中で最も低い精度（例 `C`）を採用。 |
| multiplet_id | 16文字の16進文字列 | | Multipletを表すハッシュID（`multiplet.truncate_sha256`、Multipletの場合出力）。 |
| component_index | 整数 | | Multiplet内での並び順（1始まり、Multipletの場合出力）。 |
| mutiplet_name | 文字列 | | Multipletの人間可読名（例 `C IV 1548/C IV 1551`）。単独線では空文字、Multipletの場合出力。Multipletの成分は下位準位を共有するため、`name` と同じアスタリスクが付く。 |
| tp_ref | 文字列 | | NIST Transition Probability 参照コード。 |
| line_ref | 文字列 | | NIST 波長参照コード。 |
| comment | 文字列 | | 補足メモ。合成線では `Aggregated hydrogen series (Σgi=8, Σgk=8; 7 components)` のように構成情報を付記。 |

### オプション列

- `gi_gk`（文字列）: `--include-gi-gk` 指定時のみ出力。下位・上位準位縮退度情報が保持される。ヘッダーでは `gamma` の直後に挿入される。
  - 水素系列の合成線では `Σg_i - Σg_k` の形式で両準位の縮退度合計を表記する。
- `gamma_upper` / `gamma_lower`（小数）: `--include-gamma-components` 指定時のみ出力。`gamma_upper` は上位準位からの総放射減衰率 (\\sum_i A\_{ki})、`gamma_lower` は下位準位寄与（存在する場合）の合計。どちらも指数表記（`{:.6g}`）。
- `aki_value`（小数）: `--include-aki` 指定時のみ出力。元の遷移確率 (A\_{ki})（s⁻¹）で、`gamma` 計算前の値を参照用に保持する。指数表記（`{:.6g}`）。
- `absorption_multiplet_id`（文字列）: `--include-absorption-multiplet-id` 指定時のみ追加。`multiplet_id` の直後に配置される。

### 実装メモ

- 数値は `NaN` や欠損時に空文字として書き出される（`_fmt_float/_fmt_sci/_fmt_int`）。
- `gamma` は NIST Lines の `Aki` 列を準位単位で集約し、上位準位の合計 (\\Sigma_i A\_{ki}) に加えて該当する限り下位準位の合計も足し合わせる。該当する準位情報が欠落している場合は元の `Aki` をそのまま保持する。
- Unicodeを含む種別名や準位表記もUTF-8のまま保持される。
- `name`／`mutiplet_name` 末尾のアスタリスクは下位準位の微細構造励起を表し、`lower_term`／`upper_term` 列で奇パリティを示すアスタリスク（例 `2P*`）とは無関係。
- アスタリスクの個数は、化学種の基底項の中で下位準位がエネルギー昇順で何番目か（0始まり）に一致する（`excitation.py`）。基底項の外にある下位準位（`Fe II` の `a 4F`、`H I` の `2p` など）には付与しない。VPFIT `atom.dat` の `Si II*`／`C I**`／`O I**` 表記と一致する。
