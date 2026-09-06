<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP">
<context>
    <name>ManualAnnotations</name>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="16"/>
        <source>**Colour indicator**: The colour chip beside each region matches the vertical band in the spectrum. Double-click when you need to refocus on the matching range.</source>
        <oldsource>**Browse mode side panel**: Collapse the tree while reviewing each line’s type, wavelength span, redshift, velocity window, and Needs badge. The colour chip beside each region matches the spectrum overlay; see [Browse mode side panel](#browse-mode-side-panel) for a quick reference.</oldsource>
        <translation>**色付きインジケータ**: 各領域の左側にある色がスペクトルの縦帯と対応します。色で追いづらい場合はダブルクリックで対象範囲を再表示できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="18"/>
        <source>**Fitting linked lines**: When you add a model to one linked line, components are created for every line in the link. By default, redshift, column density, b parameter, and covering factor are shared; changing one updates all linked components.</source>
        <translation>**連結ラインのフィット**: 連結されたラインの 1 つにモデルを追加すると、連結されたすべてのラインにコンポーネントが作成されます。初期状態では赤方偏移、カラム密度、b パラメータ、被覆率が共有され、いずれかを変更すると連結された全コンポーネントに反映されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="19"/>
        <source>**Link groups**: When you add a candidate using a line in a link group, a temporary line is created for every line in that group. After you register them, those lines remain linked in the project.</source>
        <oldsource>**Link groups**: When you add a candidate using a line in a link group, a temporary line is created for every line in that group. After you confirm region registration, those lines remain linked in the project.</oldsource>
        <translation>**連結グループ**: 連結グループのラインを基準に候補を追加すると、グループ内の各ラインが一時ラインとして作成されます。登録した後も、ライン同士の連結関係がプロジェクトに保存されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="20"/>
        <source>**Linked-line display**: Lines registered from the same preset link group are displayed as a single representative line with the highest f-value.</source>
        <oldsource>**Multiplet display**: Multiplets are displayed as a single representative line with the highest f-value, but optimization runs on all members.</oldsource>
        <translation>**連結ライン表示**: 同じプリセット連結グループから登録されたラインは、f 値が最大の代表ラインにまとめて表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="21"/>
        <source>**Spectrum display**: Double-click an absorption region (region) to jump the spectrum to the wavelength span that contains all of its absorption lines (lines); the coloured bands highlight that range.</source>
        <translation>**スペクトル表示**: 領域をダブルクリックすると、その領域に含まれるラインが存在する波長範囲へスペクトルが移動し、縦帯の色で範囲が示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="23"/>
        <source>A Needs badge marks regions that still require optimisation.</source>
        <translation>要最適化バッジが付いている領域は、パラメータの手動変更、コンポーネントの追加、連続光モデルの変更等で最適化が必要であることを示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="24"/>
        <source>A component that needs re-optimization shows its value without an uncertainty, since the previous fit&apos;s uncertainty no longer applies; hover the cell to see that previous value in the tooltip.</source>
        <translation>要再最適化のコンポーネントは値のみを表示し、誤差は表示しません。前回のフィットで得た誤差は現在の値に対応しないためです。セルにカーソルを合わせるとツールチップでその前回の誤差を確認できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="26"/>
        <source>A warning shown when the filter conditions conflict, such as an invalid wavelength range. It hides automatically once the conditions are fixed.</source>
        <oldsource>A temporary line is saved to a region only after the Region → Confirm sequence; pressing the Region button alone does not save it.</oldsource>
        <translation>波長範囲の指定が不正な場合など、フィルター条件が矛盾しているときに表示される警告です。条件を修正すると自動的に非表示になります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="27"/>
        <source>Absorber tree</source>
        <translation>領域ツリー</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="28"/>
        <source>Add component</source>
        <translation>コンポーネントを追加</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="29"/>
        <source>Add lines with Add Line and remove them with Remove Selected.</source>
        <translation>線種を追加 からラインを追加し、選択項目を削除 で除去します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="30"/>
        <source>Add new presets, edit membership (lines in or out), or delete unused presets.</source>
        <translation>プリセット管理ダイアログを表示し、プリセットの追加・削除・編集（スペクトル線の追加、削除）を行います。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="33"/>
        <source>Add the selected lines to the calling preset and close the dialog.</source>
        <translation>選択済みのラインを呼び出し元のプリセットへ追加してダイアログを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="34"/>
        <source>Additional Notes</source>
        <translation>補足</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="36"/>
        <source>Adjust the continuum curve with control points.</source>
        <oldsource>Adjust the continuum and masks.</oldsource>
        <translation>制御点で連続光モデルを調整します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="47"/>
        <source>Anchor line</source>
        <translation>基準線</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="48"/>
        <source>Appears when further adjustments are required for a region, highlighting items that need optimization.</source>
        <translation>コンポーネントの手動編集などが実施され、最適化が必要な領域がある場合に表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="50"/>
        <source>Apply the Planck 2018 recommended parameters (67.4, 0.315, 0.685) to the fields.</source>
        <translation>Planck 2018 の推奨パラメータ (67.4, 0.315, 0.685) を各フィールドへ適用します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="51"/>
        <source>Auto Adjust</source>
        <translation>自動調整</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="52"/>
        <source>Auto Estimate</source>
        <translation>自動推定</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="53"/>
        <source>Auto estimation overwrites existing control points; save the current state first.</source>
        <translation>自動推定は既存の制御点を上書きするため、実行前に状態を保存してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="25"/>
        <source>A link group contains at least two lines of the same ion, and each line can belong to only one link group.</source>
        <translation>連結グループには同じイオンのラインが 2 本以上必要で、各ラインが所属できる連結グループは 1 つだけです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="40"/>
        <source>Analysis Overview reviews every region&apos;s readiness, fit result, and next action.</source>
        <translation>解析概要では、各領域の解析状態、フィット結果、次の操作を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="49"/>
        <source>Apply all currently valid link suggestions to the custom preset.</source>
        <translation>現在有効な連結候補をすべてカスタムプリセットに適用します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="57"/>
        <source>Built-in presets cannot be edited; duplicate one and save it as a custom preset.</source>
        <translation>組み込みプリセットは編集できず、複製してカスタムプリセットとして保存してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="59"/>
        <source>Central canvas that shows the observed spectrum and fitted models with zoom and measurement tools.</source>
        <translation>観測フラックス、観測誤差等を表示し、ズーム等の各種操作を行うメイン画面です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="61"/>
        <source>Choose the error FITS file from a file dialog.</source>
        <translation>誤差用 FITS ファイルをファイルダイアログから選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="62"/>
        <source>Choose the flux FITS file from a file dialog.</source>
        <translation>フラックス用 FITS ファイルをファイルダイアログから選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="63"/>
        <source>Choose the preset&apos;s anchor line. When set, it is selected as the default anchor in Identify mode.</source>
        <translation>プリセットの基準線を選択します。指定すると同定モードでデフォルトで基準線として選択されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="64"/>
        <source>Choose the single line used as the identification anchor. The popup lists every line in the preset with its rest wavelength; hover an item to see its oscillator strength and full-precision wavelength.</source>
        <translation>同定の基準として使用するラインを 1 つ選択します。ポップアップにはプリセットの全ラインが静止波長付きで一覧表示されます。項目にカーソルを合わせると振動子強度（f 値）と全精度の波長を確認できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="65"/>
        <source>Choosing a language from the list updates the preview to that language.</source>
        <translation>一覧から言語を選ぶと、プレビューがその言語に切り替わります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="66"/>
        <source>Clear Control Points</source>
        <translation>制御点をクリア</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="67"/>
        <source>Clear the selected list at once when you want to start over.</source>
        <translation>選択済み一覧を一括でクリアし、やり直す際に利用します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="72"/>
        <source>Close the dialog without applying the search results.</source>
        <translation>検索結果を反映せずにダイアログを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="74"/>
        <source>Component parameter table</source>
        <translation>コンポーネントパラメータ一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="77"/>
        <source>Confirmed regions</source>
        <translation>確定領域</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="78"/>
        <source>Continuum Mode</source>
        <translation>連続光モード</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="80"/>
        <source>Control Point List</source>
        <translation>制御点リスト</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="81"/>
        <source>Control Point Table</source>
        <translation>制御点テーブル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="82"/>
        <source>Controls for adjusting the spectrum view range and scaling.</source>
        <translation>スペクトル表示範囲とスケールを調整するコントロール群です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="83"/>
        <source>Coordinate Readout</source>
        <translation>座標表示</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="84"/>
        <source>Create a link group from two or more selected lines of the same ion.</source>
        <translation>選択した同じイオンのライン 2 本以上から連結グループを作成します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="85"/>
        <source>Create an empty preset ready for any line composition.</source>
        <translation>空のプリセットを作成し、任意のライン構成を追加できる状態にします。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="86"/>
        <source>Create an empty workspace with “New Project” when starting from scratch.</source>
        <translation>最初から始める場合は［新規プロジェクト］で空のワークスペースを作成します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="87"/>
        <source>Create and adjust wavelength masks to exclude regions from the fit.</source>
        <translation>波長マスクを追加・編集して、フィットから除外する領域を制御します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="88"/>
        <source>Data Controls</source>
        <translation>データ制御パネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="90"/>
        <source>Delete selected regions or lines after reviewing the impact confirmation.</source>
        <translation>影響確認の内容を確認してから、選択した領域またはラインを削除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="91"/>
        <source>Delete selection</source>
        <translation>選択を削除</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="92"/>
        <source>Delete the selected custom preset.</source>
        <translation>選択中のカスタムプリセットを削除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="93"/>
        <source>Detail preview</source>
        <translation>詳細プレビュー</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="94"/>
        <source>Detection candidate table</source>
        <translation>検出候補一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="95"/>
        <source>Detection candidates</source>
        <translation>検出候補</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="96"/>
        <source>Discard the changes and close the dialog.</source>
        <translation>変更内容を破棄してダイアログを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="101"/>
        <source>Displays application status, messages, and cursor readouts.</source>
        <translation>現在の状態、メッセージ、カーソル情報を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="102"/>
        <source>Displays the current mode and project state.</source>
        <translation>現在のモードやプロジェクト状態を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="103"/>
        <source>Displays wavelength, flux, and action columns for every control point; double-click to edit values.</source>
        <translation>各制御点の波長・フラックス・操作列を表示します。ダブルクリックで数値を編集できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="105"/>
        <source>Double-click on the spectrum view to center the display on that wavelength (zoom level is preserved).</source>
        <translation>スペクトルビューをダブルクリックすると、その波長を中心に表示範囲が移動します（ズーム倍率は維持）。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="106"/>
        <source>Drag a rectangle to zoom into that region of the spectrum.</source>
        <translation>ドラッグした矩形範囲を拡大して表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="107"/>
        <source>Drag and drop the flux/error FITS pair or a .h5 project onto the main view.</source>
        <translation>スペクトル表示領域へ FITS（フラックスと誤差）や .h5 プロジェクトをドラッグ＆ドロップします。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="108"/>
        <source>Duplicate the selected preset into an editable copy.</source>
        <translation>選択中のプリセットを複製し、編集可能なコピーを作成します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="111"/>
        <source>Edit presets with the New / Duplicate / Rename / Delete buttons.</source>
        <translation>新規／複製／名前を変更／削除 ボタンでプリセットを編集します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="113"/>
        <source>Editing H₀, Ωm, or ΩΛ immediately recomputes Ωk and the flatness indicator.</source>
        <translation>H₀・Ωm・ΩΛ を編集すると Ωk とフラット表示が即座に再計算されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="114"/>
        <source>Element</source>
        <translation>元素</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="115"/>
        <source>Enter an element symbol, line ID, transition name, or similar for partial-match search.</source>
        <translation>元素記号やライン ID、遷移名などを入力して部分一致検索を行います。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="116"/>
        <source>Enter the instrument&apos;s resolution in the Spectral Resolution R field.</source>
        <translation>波長分解能 R フィールドに装置の分解能値を入力します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="117"/>
        <source>Enter the matter density Ωm in the range 0.000–1.000. Changing it updates Ωk.</source>
        <translation>物質密度 Ωm を 0.000 ～ 1.000 の範囲で入力します。変更すると Ωk が更新されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="119"/>
        <source>Enter the path of the FITS file containing the observed flux. Browse... also opens a file picker.</source>
        <translation>観測フラックスを含む FITS ファイルのパスを入力します。参照... でファイル選択も可能です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="120"/>
        <source>Enter the percentile threshold for automatic continuum estimation. The spectrum is divided into 100Å bins, and the flux value at the specified percentile within each bin is used as a control point. Higher values (closer to 99%) avoid absorption lines and capture peaks; lower values (closer to 50%) capture the median.</source>
        <translation>連続光自動推定のパーセンタイルしきい値を入力します。スペクトルを100Åごとのビンに分割し、各ビン内のフラックスの指定パーセンタイル位置の値を制御点とします。高い値（99%に近い）は吸収線の影響を避けてピークを捉え、低い値（50%に近い）は中央値を捉えます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="121"/>
        <source>Entered values are stored in the user settings and restored on the next launch.</source>
        <translation>入力値はユーザー設定に保存され、次回起動時に復元されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="123"/>
        <source>Export results</source>
        <translation>結果の書き出し</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="124"/>
        <source>Export the selected preset as JSON.</source>
        <translation>選択中プリセットを JSON として書き出します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="126"/>
        <source>Filter review rows by region identity or analysis state.</source>
        <translation>領域または解析状態でレビュー行を絞り込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="125"/>
        <source>Filter candidates by element in atomic-number order. Type an element symbol to select it from the suggestions; an empty field removes the restriction.</source>
        <oldsource>Filter the candidates by element. Choosing &quot;All&quot; removes the restriction.</oldsource>
        <translation>候補を原子番号順の元素で絞り込みます。元素記号を入力して候補から選択します。空欄にすると元素の制限が解除されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="127"/>
        <source>Filter warning</source>
        <translation>フィルタ警告</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="129"/>
        <source>Flux Range</source>
        <translation>フラックス範囲</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="130"/>
        <source>Flux/error FITS files that follow the `*_f.fits` and `*_e.fits` pattern are paired automatically; when you pick files with other names, use the prompt to assign flux and error roles.</source>
        <translation>`*_f.fits` / `*_e.fits` のペアは自動で割り当てられます。別名の FITS を選んだ場合はポップアップでフラックス／誤差を指定してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="131"/>
        <source>Hierarchical view of regions, lines, and components with drag-and-drop editing and double-click focusing.</source>
        <translation>領域、ラインを階層表示し、ドラッグ＆ドロップや右クリックでの編集、ダブルクリックでのフォーカス、領域名の変更ができます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="132"/>
        <source>High-S/N spectra can produce many absorption-region candidates and slow down interaction; adjust the detection threshold to keep the list manageable.</source>
        <translation>S/Nが高いスペクトルでは吸収線領域の候補が多くなり、操作が重くなることがあります。しきい値を調整してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="135"/>
        <source>Identify Mode</source>
        <translation>同定モード</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="138"/>
        <source>Identify side panel</source>
        <translation>同定モードサイドパネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="139"/>
        <source>Indicates the current subplot page and the total number of pages.</source>
        <translation>現在表示しているサブプロットページと総ページ数を示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="140"/>
        <source>Insert a new component at the selected wavelength or region.</source>
        <translation>選択した位置に新しいコンポーネントを追加します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="141"/>
        <source>Inspect observed flux, model, and residuals in the spectrum view.</source>
        <translation>スペクトル表示パネルで観測フラックス・モデル・残差を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="142"/>
        <source>Ionisation stage</source>
        <translation>電離度</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="144"/>
        <source>Key Operations</source>
        <translation>主な操作</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="145"/>
        <source>Keyword</source>
        <translation>キーワード</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="147"/>
        <source>Line species list</source>
        <translation>線種一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="148"/>
        <source>Lines already in the preset are tagged as selected, and duplicate additions are prevented automatically.</source>
        <translation>既存プリセットに含まれるラインは選択済みタグが付き、重複追加は自動で防がれます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="149"/>
        <source>Link suggestions are not applied automatically.</source>
        <translation>連結候補は自動では適用されません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="197"/>
        <source>Pick a preset in the setup header at the top of the side panel, and use the manage button to open the [Preset Management dialog](../../../menus/main_window/dialogs/PresetListDialog.md) so you can add, edit, or remove presets.</source>
        <translation>サイドパネル上部の設定ヘッダーでプリセットを選択します。［管理］ボタンから[プリセット管理ダイアログ](../../../menus/main_window/dialogs/PresetListDialog.md)を開くと、プリセットの追加・編集・削除ができます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="222"/>
        <source>Reference line selector</source>
        <translation>基準線選択</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="236"/>
        <source>Reports the New-candidate analysis range represented by the dashed boundaries. Edit the value in the setup header of the Identify side panel.</source>
        <translation>破線で示す新規候補の解析範囲を表示します。値は同定サイドパネル上部の設定ヘッダーで編集します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="249"/>
        <source>Review every region&apos;s analysis status, fit result, and next action.</source>
        <translation>各領域の解析状態、フィット結果、次の操作を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="323"/>
        <source>Switch the active candidate preset from the dropdown in the always-visible setup header.</source>
        <translation>使用するプリセットを、常時表示の設定ヘッダーのプルダウンで切り替えます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="340"/>
        <source>Turning on Apply Instrument Resolution convolves the resolution into candidate detection in Identify mode and model calculations in Analysis Region Detail.</source>
        <translation>［装置分解能を適用］をオンにすると、同定モードの候補検出と解析の領域詳細のモデル計算に分解能の効果を畳み込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="344"/>
        <source>Use Auto Estimate in the side panel to rebuild control points from the current spectrum.</source>
        <translation>サイドパネルの［自動推定］で、現在のスペクトルから制御点を作り直します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="352"/>
        <source>When a group heading in the temporary line list carries a warning mark, the lines overlap multiple existing regions; check the assignment in Analysis Structure after registering.</source>
        <translation>一時ライン一覧のグループ見出しに警告マークがある場合、ラインは複数の既存領域と重なっています。登録後に解析の構造編集で所属を確認してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="15"/>
        <source>**Analysis Structure panel**: Collapse the tree while reviewing each line’s type, wavelength span, redshift, velocity window, and Needs badge. The colour chip beside each region matches the spectrum overlay; see [Analysis Structure panel](#analysis-structure-panel) for a quick reference.</source>
        <translation>**解析の構造編集パネル**: ツリービューを折りたたみながら各ラインの線種・波長範囲・赤方偏移・速度ウィンドウ・Needs バッジを確認できます。色付きインジケータはスペクトル上の帯と一致し、詳しい操作は[解析の構造編集パネル](#解析の構造編集パネル)を参照します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="31"/>
        <source>Add selected lines to temporary list</source>
        <translation>選択した線を一時ラインに追加</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="32"/>
        <source>Add temporary lines for the selected velocity slices; use the side panel&apos;s Register action to save them to confirmed regions.</source>
        <translation>選択した速度スライスを一時ラインに追加します。確定領域へ保存するには、サイドパネルの［登録］を使用します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="35"/>
        <source>Adjust only the flux axis to fit the observed data in the currently visible wavelength range.</source>
        <translation>現在表示中の波長範囲にある観測データが収まるよう、フラックス軸だけを調整します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="37"/>
        <source>Adjust the wavelength and flux ranges with the data control panel. Velocity controls depend on the active mode.</source>
        <translation>データ制御パネルで波長とフラックスの範囲を調整します。速度制御の利用可否は現在のモードによって異なります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="39"/>
        <source>Analysis Mode</source>
        <translation>解析モード</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="41"/>
        <source>Analysis Region Detail panel</source>
        <translation>解析の領域詳細パネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="42"/>
        <source>Analysis Region Detail prepares fitting conditions, runs the optimiser, and reviews one region&apos;s result.</source>
        <translation>解析の領域詳細では、1つの領域についてフィット条件を整え、解析を実行して結果を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="43"/>
        <source>Analysis Structure edits the region and line hierarchy from Overview.</source>
        <translation>解析の構造編集では、概要から領域とラインの階層を編集します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="44"/>
        <source>Analysis Structure panel</source>
        <translation>解析の構造編集パネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="45"/>
        <source>Analysis review table</source>
        <translation>解析レビュー表</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="55"/>
        <source>Back to Spectrum</source>
        <translation>スペクトルに戻る</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="58"/>
        <source>Cancel</source>
        <translation>キャンセル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="70"/>
        <source>Close Project</source>
        <translation>プロジェクトを閉じる</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="71"/>
        <source>Close the Velocity Plot and return to the standard spectrum view.</source>
        <translation>速度プロットを閉じ、標準のスペクトル表示に戻ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="73"/>
        <source>Compare the current region&apos;s lines on a shared velocity axis. Display range reframes every subplot and page without changing the line analysis ranges.</source>
        <oldsource>Compare the current region&apos;s lines on a shared velocity axis. Display half-width reframes every subplot and page without changing the line analysis ranges.</oldsource>
        <translation>現在の領域のラインを共通の速度軸で比較します。［表示範囲］を変更すると、ライン解析範囲を変えずにすべてのサブプロットとページの表示範囲が変わります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="75"/>
        <source>Confirm what happens to unsaved changes before the current project is closed.</source>
        <translation>現在のプロジェクトを閉じる前に、未保存の変更をどう扱うかを確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="97"/>
        <source>Discard the unsaved changes and close the project.</source>
        <translation>未保存の変更を破棄してプロジェクトを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="98"/>
        <source>Display</source>
        <translation>表示</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="100"/>
        <source>Display range</source>
        <oldsource>Display half-width</oldsource>
        <translation>表示範囲</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="104"/>
        <source>Don&apos;t Save</source>
        <translation>保存しない</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="109"/>
        <source>Each row shows a candidate&apos;s wavelength range, σ score, and status (Unassigned, Tentative, or Registered). A single click only selects a row; double-click it or press Enter to move to the candidate position, then Shift+click the absorption center to add temporary lines.</source>
        <translation>各行に候補の波長範囲、σ値、状態（未対応・仮対応・登録済み）が表示されます。1回のクリックでは行が選択されるだけで、ダブルクリックまたはEnterキーで候補位置へ移動します。移動後に吸収中心をShift+クリックすると一時ラインが追加されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="110"/>
        <source>Edit Analysis range [km/s] on a line or multiplet row to set the interval used for analysis.</source>
        <oldsource>Edit Analysis half-width [km/s] on a line or multiplet row to set the interval used for analysis.</oldsource>
        <translation>ラインまたは多重線行の［解析範囲 [km/s]］を編集し、解析に使用する範囲を設定します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="118"/>
        <source>Enter the minimum and maximum within 0–50000 Å to narrow the searched wavelength band. An empty field removes the limit on that side.</source>
        <translation>0～50000 Åの範囲で最小値と最大値を入力し、検索対象の波長帯を絞り込みます。空欄にすると該当側の制限が解除されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="122"/>
        <source>Explain that closing returns to Start mode and that the project can be reopened from File &gt; Open Project.</source>
        <translation>閉じると開始モードに戻ること、［ファイル］&gt;［プロジェクトを開く］から再び開けることを案内します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="128"/>
        <source>Fit view to analysis ranges</source>
        <translation>解析範囲に合わせる</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="137"/>
        <source>Identify mode focuses on reviewing detections and assigning absorption lines to species and regions.</source>
        <translation>同定モードでは、検出結果の確認と、吸収線の線種・領域への対応付けを行います。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="143"/>
        <source>Keep the project open and leave it unchanged.</source>
        <translation>プロジェクトを開いたまま、何も変更せずに戻ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="150"/>
        <source>Linked lines and lines</source>
        <translation>連結ラインとライン</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="151"/>
        <source>Lists temporary lines grouped by the registration result. Group headings show whether the lines will create a new region or be added to an existing one; a warning mark flags overlaps with multiple existing regions.</source>
        <translation>一時ラインを登録結果ごとにグループ化して表示します。グループ見出しには、新規領域になるか既存領域へ追加されるかが表示され、複数の既存領域と重なる場合は警告マークが付きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="152"/>
        <source>Lists the lines scheduled for addition; select unwanted ones to remove them.</source>
        <translation>追加予定のラインを一覧表示し、不要なものを選択して削除できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="153"/>
        <source>Lists the preset&apos;s absorption lines and shows their link-group membership in the Link column. Wavelengths, f-values, and link labels are read-only.</source>
        <translation>プリセットに含まれる吸収線を一覧表示し、［連結］列に連結グループへの所属を示します。波長、f 値、連結ラベルは読み取り専用です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="154"/>
        <source>Load a preset JSON file and add it to the current list.</source>
        <translation>プリセットのJSONファイルを読み込み、現在の一覧へ追加します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="155"/>
        <source>Load an existing project file.</source>
        <translation>既存のプロジェクトファイルを読み込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="156"/>
        <source>Load observed flux and error FITS files to start a new project.</source>
        <translation>観測フラックスと誤差の FITS ファイルを読み込み、新規プロジェクトを開始します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="157"/>
        <source>Loading resources can take a few seconds after changing the language.</source>
        <translation>言語変更後はリソースの読み込みに数秒要する場合があります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="159"/>
        <source>Manage absorption-line presets and choose which lines should be identified and fitted together.</source>
        <oldsource>Manage absorption-line presets and declare which lines should be identified and fitted together.</oldsource>
        <translation>吸収線プリセットを管理し、同定とフィットで一緒に扱うラインを設定します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="160"/>
        <source>Manage presets</source>
        <translation>プリセット管理</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="161"/>
        <source>Mask panel</source>
        <translation>除外領域</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="163"/>
        <source>Merge the selected regions after reviewing the impact confirmation.</source>
        <translation>影響確認の内容を確認してから、選択した領域を統合します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="164"/>
        <source>Message Area</source>
        <translation>メッセージ欄</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="165"/>
        <source>Mode Bar</source>
        <translation>モードバー</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="166"/>
        <source>Mode Indicator</source>
        <translation>モードインジケーター</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="167"/>
        <source>Mode Info Area</source>
        <translation>モード情報エリア</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="168"/>
        <source>Mode Subtitle</source>
        <translation>モードサブタイトル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="169"/>
        <source>More actions</source>
        <translation>その他の操作</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="170"/>
        <source>Narrow down the candidates with filters for keyword, element, ionisation stage, and wavelength range.</source>
        <translation>キーワードや元素・イオン段階、波長範囲でフィルタを設定して候補を絞り込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="171"/>
        <source>Needs optimization badge</source>
        <translation>要最適化バッジ</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="172"/>
        <source>New-candidate range</source>
        <oldsource>New-candidate half-width</oldsource>
        <translation>新規候補の範囲</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="173"/>
        <source>Next page</source>
        <translation>次のページ</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="174"/>
        <source>No Control Points Yet</source>
        <translation>制御点がありません</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="175"/>
        <source>No control points are registered. Right-click the spectrum or use the buttons to add new ones.</source>
        <translation>まだ制御点が登録されていません。スペクトル上で右クリックするか、ボタン操作で制御点を追加できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="176"/>
        <source>No spectrum is shown in this mode. Drag and drop two FITS files (observed flux and error) or a project file (.h5) here. You can also use File &gt; Open. The data control panel is hidden in Start mode, but it appears beneath the spectrum view after you switch to another mode.</source>
        <translation>このモードではスペクトルは表示されません。ここに FITS ファイル（観測フラックスと観測誤差の2ファイル）またはプロジェクトファイル（.h5）をドラッグ＆ドロップしてください。メニューの「ファイル &gt; 開く」からも読み込めます。データ制御パネルはスタートモードでは表示されませんが、他のモードに切り替えるとスペクトルの下部に現れます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="177"/>
        <source>No spectrum or data controls appear until data has been loaded.</source>
        <translation>データを読み込むまでスペクトルやデータ制御パネルは表示されません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="179"/>
        <source>Notes &amp; Caveats</source>
        <translation>注意点</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="183"/>
        <source>Open Analysis Structure without leaving the Analysis workspace.</source>
        <translation>解析ワークスペースから離れずに構造編集を開きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="184"/>
        <source>Open Display in the data control panel or right-click the spectrum, or press M, to show Component profiles; each component draws its own curve in the colour of its marker and label, and this toggle is disabled outside Region Detail.</source>
        <translation>データ制御パネルの［表示］を開くか、スペクトルを右クリックするか、M キーを押すと、［コンポーネントプロファイル］を表示できます。各コンポーネントは、自身のマーカー線とラベルに合わせた色でプロファイル曲線を描画します。この項目は領域詳細以外では無効になります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="185"/>
        <source>Open Display in the data control panel to show or hide the error spectrum.</source>
        <translation>データ制御パネルの［表示］を開き、［誤差スペクトル］の表示・非表示を切り替えます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="186"/>
        <source>Open Observation Data</source>
        <translation>観測データを開く</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="187"/>
        <source>Open Project</source>
        <translation>プロジェクトを開く</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="188"/>
        <source>Open a popup with two checkable display toggles, &quot;Error spectrum&quot; (on by default) and &quot;Component profiles&quot; (off by default). Error spectrum shows or hides the error spectrum in the spectrum view and velocity subplots. Component profiles draws each absorption component&apos;s own profile curve in its identity colour, matching that component&apos;s marker line and label; it is available only in Analysis Region Detail and is disabled elsewhere with the tooltip &quot;Available in Analysis region detail&quot;. Component profiles has the shortcut M. Both toggles also appear in the spectrum view&apos;s right-click menu.</source>
        <translation>チェック可能な表示切り替え項目を2つ持つポップアップを開きます。［誤差スペクトル］（既定でオン）と［コンポーネントプロファイル］（既定でオフ）です。［誤差スペクトル］はスペクトルビューと速度サブプロットの誤差スペクトルの表示・非表示を切り替えます。［コンポーネントプロファイル］は各吸収線コンポーネントのプロファイル曲線を、そのコンポーネントのマーカー線とラベルに合わせた色で描画します。この項目は解析の領域詳細でのみ利用でき、それ以外の画面では無効になり、「解析モードの領域詳細で利用できます」というツールチップが表示されます。［コンポーネントプロファイル］のショートカットキーは M です。両方の項目はスペクトルビューの右クリックメニューにも表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="189"/>
        <source>Open existing projects through the context bar&apos;s &quot;Open Project&quot; action.</source>
        <translation>モードバーの［プロジェクトを開く］から既存のプロジェクトを読み込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="190"/>
        <source>Open region</source>
        <translation>領域を開く</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="191"/>
        <source>Open the absorption-line database search dialog and add new absorption lines to the preset.</source>
        <translation>吸収線データベース検索ダイアログを開き、プリセットへ新しい吸収線を追加します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="192"/>
        <source>Open the low-emphasis actions menu. Choose Clear All to empty the temporary line list.</source>
        <translation>低強調の操作メニューを開きます。［全消去］を選択すると一時ライン一覧が空になります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="194"/>
        <source>Organise the additions in the selected list and press Add Lines to apply them to the calling preset.</source>
        <translation>選択済みリストで追加対象を整理し、ラインを追加ボタンで呼び出し元のプリセットへ反映します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="195"/>
        <source>Page status</source>
        <translation>ページ状況</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="196"/>
        <source>Percentile</source>
        <translation>パーセンタイル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="198"/>
        <source>Place the cursor over an absorption feature and press V to verify that exact position in the Velocity Plot; hold Shift first when you want to see the all-species preview before deciding. Right-clicking the spectrum and selecting [Show Velocity Plot (V)] opens the plot at the position you right-clicked.</source>
        <translation>吸収特徴にカーソルを合わせてVを押すと、その正確な位置を速度プロットで検証できます。判断する前に全線種プレビューを確認したいときは、先にShiftを押します。スペクトルを右クリックして［速度プロットを表示 (V)］を選択すると、右クリックした位置でプロットが開きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="199"/>
        <source>Preset list</source>
        <translation>プリセット一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="200"/>
        <source>Preset selector</source>
        <translation>プリセット選択</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="201"/>
        <source>Press Apply Planck2018 to reset the fields to the Planck 2018 recommended values.</source>
        <translation>Planck2018 を適用 を押すとプランク2018の推奨値にフィールドをリセットします。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="202"/>
        <source>Press Cancel to close without changing anything.</source>
        <translation>キャンセルを押すと変更せずに閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="203"/>
        <source>Press Cancel to keep working in the current project.</source>
        <translation>［キャンセル］を押すと、現在のプロジェクトでの作業を続けます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="204"/>
        <source>Press Don&apos;t Save to close the project and lose the unsaved changes.</source>
        <translation>［保存しない］を押すと、未保存の変更を失ったままプロジェクトを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="206"/>
        <source>Press OK to apply the selected language immediately.</source>
        <translation>OK を押すと選択した言語が即時適用されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="208"/>
        <source>Press OK to save the settings and apply them to the main window.</source>
        <translation>OK を押すと設定が保存されメインウィンドウへ反映されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="209"/>
        <source>Press OK to validate the selected files and load them into the project.</source>
        <translation>OK を押すと選択したファイルが検証され、プロジェクトへ読み込まれます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="212"/>
        <source>Press Save to write the project to disk and then close it.</source>
        <translation>［保存］を押すと、プロジェクトを保存してから閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="213"/>
        <source>Press V with the cursor over an absorption feature to open the plot immediately at that exact wavelength, or right-click the spectrum and select [Show Velocity Plot (V)]. Press V again or select [Back to Spectrum] to return. Dashed boundaries show the New-candidate analysis range; Display range reframes every subplot without changing candidate data.</source>
        <translation>吸収特徴にカーソルを合わせてVを押すか、スペクトルを右クリックして［速度プロットを表示 (V)］を選択すると、その波長でプロットが開きます。もう一度Vを押すか［スペクトルに戻る］を選択すると元の表示に戻ります。破線は新規候補の解析範囲を示し、［表示範囲］は候補データを変更せずにすべてのサブプロットを表示し直します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="214"/>
        <source>Pressing Register saves the temporary lines to regions immediately without a confirmation step; use Undo when you need to revert a registration.</source>
        <translation>［登録］を押すと、確認ステップなしで一時ラインが即座に領域へ保存されます。登録を取り消すときは元に戻す操作を使用してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="215"/>
        <source>Previous page</source>
        <translation>前のページ</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="216"/>
        <source>Quick Actions</source>
        <translation>クイック操作</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="218"/>
        <source>Recalculate Display range from New-candidate range. This action changes only the Velocity Plot view.</source>
        <oldsource>Recalculate Display half-width from New-candidate half-width. This action changes only the Velocity Plot view.</oldsource>
        <translation>［新規候補の範囲］から［表示範囲］を再計算します。この操作で変わるのは速度プロットの表示だけです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="219"/>
        <source>Recalculate Display range from the current region&apos;s line analysis ranges. This action changes only the Velocity Plot view.</source>
        <oldsource>Recalculate Display half-width from the current region&apos;s line analysis ranges. This action changes only the Velocity Plot view.</oldsource>
        <translation>現在の領域のライン解析範囲から［表示範囲］を再計算します。この操作で変わるのは速度プロットの表示だけです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="220"/>
        <source>Recalculates control points from the current spectrum and replaces existing points with the new estimate.</source>
        <translation>現在表示中のスペクトルから制御点を再計算し、既存の制御点を新しい推定値で置き換えます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="221"/>
        <source>Redo</source>
        <translation>やり直し</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="231"/>
        <source>Remove the highlighted temporary lines from the list.</source>
        <translation>選択中の一時ラインを一覧から削除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="237"/>
        <source>Reports the current line analysis ranges represented by dashed boundaries.</source>
        <oldsource>Reports the current line analysis half-widths represented by dashed boundaries.</oldsource>
        <translation>破線で示す現在のライン解析範囲を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="241"/>
        <source>Restore the wavelength and flux ranges saved for the current view. If no view range is saved, show the full spectrum.</source>
        <translation>現在の表示用に保存された波長範囲とフラックス範囲へ戻します。表示範囲が保存されていない場合は、スペクトル全体を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="252"/>
        <source>Right-click a row in the region list and choose &quot;Delete region…&quot;, or press the Delete key, to remove a region after a confirmation.</source>
        <translation>領域一覧の行を右クリックして［領域を削除…］を選ぶか、Delete キーを押すと、確認のうえで領域を削除できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="253"/>
        <source>Right-click the spectrum to add a control point, and drag existing points to shape the continuum curve.</source>
        <translation>スペクトルを右クリックして制御点を追加し、既存の制御点をドラッグして連続光モデルを整えます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="254"/>
        <source>Run fit</source>
        <translation>フィットを実行</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="257"/>
        <source>Save temporary groups to regions immediately. With no selection, the label is Register all (N groups); with selected rows, it is Register selected (N groups). Registration can be undone.</source>
        <oldsource>Save temporary groups to regions immediately. With no selection, Register all shows the total group count; with selected rows, Register selected shows the selected group count. Registration can be undone.</oldsource>
        <translation>一時グループを領域へ即座に保存します。未選択時は［すべて登録 (N組)］、行の選択時は［選択を登録 (N組)］と表示されます。登録は元に戻す操作で取り消せます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="260"/>
        <source>Save the project, then close it and return to Start mode.</source>
        <translation>プロジェクトを保存してから閉じ、開始モードに戻ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="265"/>
        <source>Select a row in the parameter table to emphasise that component in the spectrum view; its label reads bold and keeps the full name on the top row, while crowded neighbours shorten and alternate onto a second row.</source>
        <translation>パラメータ表の行を選択すると、そのコンポーネントがスペクトル表示で強調されます。ラベルは太字になり、上段にフルネームが表示されます。ラベルが混み合う場合は、周囲のラベルが短縮され、上下 2 段に交互に配置されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="279"/>
        <source>Set the symmetric analysis range used by the next Shift preview and candidates added afterward. Existing temporary lines, registration grouping, and Velocity Plot Display range do not change.</source>
        <oldsource>Set the symmetric analysis half-width used by the next Shift preview and candidates added afterward. Existing temporary lines, registration grouping, and Velocity Plot Display half-width do not change.</oldsource>
        <translation>次のShiftプレビューと、これから追加する候補に使用する左右対称の解析範囲を設定します。既存の一時ライン、登録時の束ね結果、速度プロットの［表示範囲］は変更しません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="280"/>
        <source>Set the symmetric view range shared by every Identify Velocity Plot subplot and page. This display-only value does not change New-candidate range, temporary lines, grouping, or scientific Undo history.</source>
        <oldsource>Set the symmetric view range shared by every Identify Velocity Plot subplot and page. This display-only value does not change New-candidate half-width, temporary lines, grouping, or scientific Undo history.</oldsource>
        <translation>同定の速度プロットにあるすべてのサブプロットとページで共有する左右対称の表示範囲を設定します。この表示専用値は、新規候補の範囲、一時ライン、束ね結果、科学操作のUndo履歴を変更しません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="281"/>
        <source>Set the symmetric view range shared by every Velocity Plot subplot and page. This display-only value does not change line analysis ranges or scientific Undo history.</source>
        <translation>すべての速度プロットのサブプロットとページで共有する対称表示範囲を設定します。この表示専用値は、ライン解析範囲や科学的なUndo履歴を変更しません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="287"/>
        <source>Show the name of the project that is about to be closed.</source>
        <translation>閉じようとしているプロジェクトの名称を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="292"/>
        <source>Shows readiness counts, the read-only structure of the selected region, and actions to open or edit it.</source>
        <translation>解析状態の件数、選択中の領域の読み取り専用の構造、開く／編集の操作を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="296"/>
        <source>Shows the current region and line context for the active Velocity Plot.</source>
        <translation>現在の領域と、表示中の速度プロットのラインコンテキストを示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="298"/>
        <source>Shows the hierarchy of confirmed regions and their lines. A single click only selects a row and does not move the spectrum view; press Enter or double-click a region or line to move the spectrum view to its range while Identify mode stays active. Right-click a region or line row to select it and choose Open region to open the region in Analysis Region Detail, or Edit region to open it in Analysis Structure; a right-click on a line row targets its parent region.</source>
        <translation>確定領域とラインの階層を表示します。単クリックは行を選択するだけで、スペクトル表示は移動しません。領域行またはライン行を選んで Enter キーを押すか、行をダブルクリックすると、同定モードのまま、スペクトル表示が対象の波長域へ移動します。領域行またはライン行を右クリックすると、その行が選択され、［領域を開く］で解析の領域詳細が、［領域を編集］で解析の構造編集が開きます。ライン行を右クリックした場合は、親となる領域が対象になります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="299"/>
        <source>Shows the linked-line and line counts for the selected region. When there are six or fewer linked lines, it also shows each redshift and transition name.</source>
        <translation>選択中の領域に含まれる連結ラインとラインの数を表示します。連結ラインが6件以下の場合は、各連結ラインの赤方偏移と遷移名も表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="301"/>
        <source>Shows the target line, redshift, and observed wavelength for the active Velocity Plot.</source>
        <translation>表示中の速度プロットについて、対象ライン、赤方偏移、観測波長を示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="304"/>
        <source>Single-column panel ordered along the identify workflow — the preset setup header, detection candidates, temporary lines with registration, and confirmed regions. Drag the grip handles between sections to resize them. See “Side Panel Details” below for control-by-control guidance.</source>
        <translation>同定ワークフローの順に、プリセットの設定ヘッダー、検出候補、一時ラインと登録、確定領域を 1 列に並べたパネルです。セクション間のグリップハンドルをドラッグすると高さを調整できます。各コントロールの説明は後述の「サイドパネルの詳細」を参照してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="312"/>
        <source>Split</source>
        <translation>分割</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="314"/>
        <source>Stale count</source>
        <translation>結果が古い件数</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="317"/>
        <source>State that the current project has unsaved changes and ask whether to save them.</source>
        <translation>現在のプロジェクトに未保存の変更があることを示し、保存するかどうかを確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="325"/>
        <source>Temporary lines</source>
        <translation>一時ライン</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="225"/>
        <source>Region selector</source>
        <translation>領域セレクター</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="17"/>
        <source>**Edit regions**: Rearrange lines and use the visible Structure actions or context menu to merge, split, unlink, or delete items (see [Analysis Structure](../../../operations/analysis-structure.md)). Press Back to Overview at the top of the panel to return to Analysis Overview.</source>
        <translation>**領域を編集**: ラインを移動し、構造編集のボタンまたはコンテキストメニューから統合、分割、連結解除、削除を実行します（[解析の構造編集](../../../operations/analysis-structure.md)を参照してください）。パネル上部の［概要へ戻る］を押すと解析の概要に戻ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="22"/>
        <source>**Velocity window**: Each line heading in the tree shows its velocity window inline (±… km/s).</source>
        <translation>**速度ウィンドウ**: ツリーの各ライン見出しに速度ウィンドウ（±… km/s）が表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="38"/>
        <source>Adjust the ΛCDM parameters used to compute comoving distance and lookback time in the analysis.</source>
        <translation>解析で共動距離とルックバックタイムの計算に用いる ΛCDM パラメータを調整します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="54"/>
        <source>Back to Overview</source>
        <translation>概要へ戻る</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="56"/>
        <source>Bottom pane</source>
        <translation>下部ペイン</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="60"/>
        <source>Choose the display language of the application. The preview below updates to the selected language.</source>
        <translation>アプリケーションの表示言語を選びます。下のプレビューが選んだ言語に切り替わります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="68"/>
        <source>Click a status count in the summary panel to filter the region list.</source>
        <translation>サイドパネルの状態の件数をクリックすると、領域一覧を絞り込めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="69"/>
        <source>Click to expand or collapse the confirmed-region list. While collapsed, the summary shows the region count and a representative region and line.</source>
        <translation>選択すると確定領域一覧を展開・折りたたみできます。折りたたみ中の要約には、領域数と代表的な領域およびラインが表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="76"/>
        <source>Confirmed Regions section header</source>
        <translation>確定領域セクション見出し</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="79"/>
        <source>Continuum mode shapes the continuum curve so later analysis stays stable.</source>
        <translation>連続光モードは連続光モデルを調整し、後続の解析を安定させます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="89"/>
        <source>Delete</source>
        <translation>削除</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="99"/>
        <source>Display language</source>
        <translation>表示言語</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="112"/>
        <source>Edit region</source>
        <translation>領域を編集</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="133"/>
        <source>Hosts the component parameter table while Region Detail is open. Drag the splitter handle above it to resize.</source>
        <translation>領域詳細を開いている間、コンポーネントのパラメータテーブルを表示します。上のスプリッターハンドルをドラッグすると高さを変更できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="134"/>
        <source>Hosts the region list below the spectrum. Drag the splitter handle above it to resize.</source>
        <translation>スペクトルの下に領域一覧を表示します。上のスプリッターハンドルをドラッグすると高さを変更できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="136"/>
        <source>Identify absorption lines and assign them to line species and regions.</source>
        <translation>吸収ラインを同定し、線種と領域へ対応付けます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="146"/>
        <source>Latest count</source>
        <translation>最新の件数</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="158"/>
        <source>Lock or unlock parameters in the parameter table shown in the bottom pane to define the search space.</source>
        <translation>下部ペインのパラメータテーブルでパラメータを固定／解放し、探索範囲を設定します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="162"/>
        <source>Merge</source>
        <translation>統合</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="178"/>
        <source>Not analyzed count</source>
        <translation>未解析の件数</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="180"/>
        <source>Number of regions that have not been fitted yet. Click to filter the region list.</source>
        <translation>まだフィットしていない領域の数です。クリックすると領域一覧を絞り込めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="181"/>
        <source>Number of regions whose fit result is outdated. Click to filter the region list.</source>
        <translation>フィット結果が古くなった領域の数です。クリックすると領域一覧を絞り込めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="182"/>
        <source>Number of regions whose fit result is up to date. Click to filter the region list.</source>
        <translation>フィット結果が最新の領域の数です。クリックすると領域一覧を絞り込めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="205"/>
        <source>Press Enter or double-click a row in the region list to open the region in Region Detail.</source>
        <translation>領域一覧の行で Enter を押すかダブルクリックすると、その領域を領域詳細で開きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="207"/>
        <source>Press OK to confirm the value, or Cancel to keep the existing setting.</source>
        <translation>［OK］で値を確定し、［キャンセル］で現在の設定を維持します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="210"/>
        <source>Press Register all (N groups), or select rows and press Register selected (N groups), to save temporary groups immediately; the status bar reports the created or extended regions, and Undo reverts the registration.</source>
        <oldsource>Press Register all, or select rows and press Register selected, to save temporary groups immediately; the status bar reports the created or extended regions, and Undo reverts the registration.</oldsource>
        <translation>［すべて登録 (N組)］、または行を選択して［選択を登録 (N組)］を押すと、一時グループが即座に保存されます。作成・追加された領域はステータスバーに表示され、元に戻す操作で登録を取り消せます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="211"/>
        <source>Press Run fit and adjust masks to refine residuals.</source>
        <translation>［フィットを実行］を押し、マスクを調整して残差を詰めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="226"/>
        <source>Register</source>
        <translation>登録</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="227"/>
        <source>Registration result</source>
        <translation>登録結果</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="228"/>
        <source>Remove every link group containing one of the selected rows. The lines remain in the preset.</source>
        <translation>選択行を含む連結グループをすべて解除します。ライン自体はプリセットに残ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="230"/>
        <source>Remove the absorption lines selected in the table from the preset.</source>
        <translation>テーブルで選択した吸収線をプリセットから削除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="232"/>
        <source>Remove the line species highlighted in the selected list.</source>
        <translation>選択済み一覧でハイライトしているスペクトル線種を除外します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="233"/>
        <source>Removes every registered control point and returns the continuum to a flat baseline.</source>
        <translation>登録済みの制御点をすべて削除し、連続光をフラットな状態に戻します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="234"/>
        <source>Rename the preset. Only custom presets can be edited.</source>
        <translation>プリセット名を変更します。カスタムプリセットのみ編集可能です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="235"/>
        <source>Repeat the last undone action.</source>
        <translation>取り消した操作を再実行します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="238"/>
        <source>Reports the cursor position in wavelength or velocity.</source>
        <translation>カーソル位置の波長や速度を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="239"/>
        <source>Reset</source>
        <translation>リセット</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="240"/>
        <source>Reset all entered filter conditions and return the search results to the initial state.</source>
        <translation>入力したフィルタ条件をすべてリセットし、検索結果を初期状態に戻します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="242"/>
        <source>Results summary</source>
        <translation>結果サマリー</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="243"/>
        <source>Return to Analysis Overview (Alt+Left).</source>
        <translation>解析の概要に戻ります（Alt+←）。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="244"/>
        <source>Return to the standard spectrum view and re-enable wavelength controls.</source>
        <translation>速度プロットを閉じて通常のスペクトル表示に戻ります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="245"/>
        <source>Revert the last action.</source>
        <translation>直前の操作を取り消します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="247"/>
        <source>Review database-derived link suggestions and use Apply all to accept every valid suggestion.</source>
        <translation>ラインデータベースから提示された連結候補を確認し、［すべて適用］で有効な候補を一括適用します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="248"/>
        <source>Review each control point&apos;s wavelength and flux, then edit or delete entries as needed.</source>
        <translation>登録済みの制御点を波長とフラックスで一覧し、必要に応じて編集・削除できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="250"/>
        <source>Review the selected line&apos;s transition levels, oscillator strength, references, and other details as text.</source>
        <translation>選択したラインの遷移レベルや振動子強度、文献情報などをテキストで確認できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="251"/>
        <source>Review the shared context bar, spectrum view, and status bar that appear in every mode.</source>
        <translation>メインウィンドウに共通するコンテキストメニューやスペクトル表示エリアの役割を概観します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="255"/>
        <source>Save</source>
        <translation>保存</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="256"/>
        <source>Save optimization results and statistics as CSV.</source>
        <translation>最適化結果や統計値をCSV形式でエクスポートします。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="258"/>
        <source>Save the current project state to disk.</source>
        <translation>現在の作業内容をプロジェクトファイルに保存します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="259"/>
        <source>Save the current settings and close the dialog.</source>
        <translation>現在の設定を保存してダイアログを閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="261"/>
        <source>Search results</source>
        <translation>検索結果一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="262"/>
        <source>Search the absorption-line database for lines and bring them into presets or Identify mode.</source>
        <translation>吸収線データベースからラインを検索し、プリセットや同定モードに取り込むためのダイアログです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="263"/>
        <source>Select a line in the result list and check its transition data and f-value in the detail preview on the right.</source>
        <translation>結果一覧でラインを選択し、右側の詳細プレビューで遷移情報や f 値を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="266"/>
        <source>Select the error FITS file as well if needed.</source>
        <translation>必要に応じて誤差用 FITS ファイルも選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="267"/>
        <source>Select the flux FITS file with the Browse... button.</source>
        <translation>参照... ボタンからフラックス用 FITS ファイルを選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="268"/>
        <source>Select two or more rows and use Link selected lines to create a link group; select a linked row and use Unlink to remove its group.</source>
        <translation>2 行以上を選択して［選択行を連結］で連結グループを作成します。連結済みの行を選択して［連結解除］を押すと、そのグループを解除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="269"/>
        <source>Selected Line List</source>
        <translation>選択済み線種一覧</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="270"/>
        <source>Selected lines</source>
        <translation>選択済みライン</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="272"/>
        <source>Selecting a preset in the left list shows its composition on the right.</source>
        <translation>左側のリストでプリセットを選ぶと右側に構成が表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="273"/>
        <source>Selecting or clearing any member of a multiplet applies the same state to every member. When opened from preset management, an explicitly selected multiplet is also proposed as a preset link group.</source>
        <translation>マルチプレットのどのメンバーを選択または解除しても、全メンバーに同じ状態が適用されます。プリセット管理から開いた場合、明示的に選択したマルチプレットはプリセット連結グループの候補にもなります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="274"/>
        <source>Selection area</source>
        <translation>選択エリア</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="275"/>
        <source>Set the dark-energy density ΩΛ in the range 0.000–1.000. It feeds into the Ωk calculation.</source>
        <translation>ダークエネルギー密度 ΩΛ を 0.000 ～ 1.000 の範囲で設定します。Ωk の計算に反映されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="276"/>
        <source>Set the instrument&apos;s spectral resolution R and choose how it is applied to model calculations.</source>
        <translation>観測装置の波長分解能 R を設定し、モデル計算への反映方法を選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="277"/>
        <source>Set the lower and upper flux limits.</source>
        <translation>フラックス表示の上下限を設定します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="278"/>
        <source>Set the minimum and maximum wavelengths shown.</source>
        <translation>表示する波長の最小値と最大値を設定します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="282"/>
        <source>Share presets as JSON files with Import... / Export....</source>
        <translation>インポート...／エクスポート... で JSONファイルとして共有できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="283"/>
        <source>Shift+click an absorption feature on the spectrum to add temporary lines; the temporary line list always shows how they will be grouped into regions.</source>
        <translation>スペクトル上の吸収を Shift+クリックすると一時ラインが追加されます。一時ライン一覧には、領域へどのように束ねられるかが常に表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="284"/>
        <source>Shortcuts for estimating or resetting continuum control points without leaving the panel.</source>
        <translation>連続光の制御点を自動推定したり、既存ポイントをリセットしたりするショートカットです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="285"/>
        <source>Show a sample of how menus and buttons appear in the selected language.</source>
        <translation>選択した言語でメニューやボタンがどのように表示されるかをサンプル表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="288"/>
        <source>Shown in the bottom pane while Region Detail is open. Edit component parameters and each line&apos;s Analysis range [km/s] for the selected region. Component rows leave the analysis-range cell empty. Each parameter value cell combines the shared tie label, fitted value, and uncertainty in one display; right-click a column header to show or hide columns, and drag a header to reorder columns (visibility, order, and width are remembered for next time).</source>
        <translation>領域詳細を開いている間、下部ペインに表示されます。選択した領域の成分パラメータと各ラインの［解析範囲 [km/s]］を編集します。成分行の解析範囲セルは空欄です。各パラメータ値セルには、共有ラベル、フィット値、誤差がまとめて表示されます。列見出しを右クリックすると列の表示/非表示を切り替えられ、見出しをドラッグすると列を並べ替えられます（表示状態、順序、幅は次回まで保存されます）。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="289"/>
        <source>Shows a short description of the active mode.</source>
        <translation>選択中モードの補足説明を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="290"/>
        <source>Shows link groups suggested from multiplets in the line database. Suggestions remain pending until applied.</source>
        <translation>ラインデータベースのマルチプレットから提案された連結グループを表示します。候補は適用するまで保留状態です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="291"/>
        <source>Shows progress and notification messages.</source>
        <translation>進行状況や通知メッセージを表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="293"/>
        <source>Shows supplemental context for the active mode.</source>
        <translation>モードの補足説明や状態を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="295"/>
        <source>Shows the absorption-line candidates with wavelength, type, f-value, and more. Click a column header to change the sort order.</source>
        <translation>吸収線候補を波長、種別、f 値などとともに表示します。列ヘッダーをクリックするとソート順を切り替えられます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="297"/>
        <source>Shows the fit status, χ² statistics, and component count for the region. A note explains the next step while fitting is unavailable.</source>
        <translation>領域のフィット状態、χ² 統計、コンポーネント数を表示します。フィットできない間は、次に行う操作を示す注記が表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="300"/>
        <source>Shows the result after a successful registration. The message clears when the temporary-line workflow changes again.</source>
        <translation>登録に成功した後、その結果を表示します。一時ラインのワークフローが再び変化するとメッセージは消去されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="46"/>
        <source>Analysis-range summary</source>
        <translation>解析範囲の要約</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="193"/>
        <source>Open the selected region in Analysis Region Detail.</source>
        <translation>選択した領域を解析の領域詳細で開きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="217"/>
        <source>Readiness filter</source>
        <translation>解析状態フィルター</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="223"/>
        <source>Region filter</source>
        <translation>領域フィルター</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="224"/>
        <source>Region review rows</source>
        <translation>領域レビュー行</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="229"/>
        <source>Remove only the selected scientific link while keeping the lines.</source>
        <translation>ラインを残したまま、選択した科学的な連結だけを解除します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="246"/>
        <source>Review all regions in Overview, edit Structure, and analyze one region in Detail.</source>
        <translation>概要ですべての領域を確認し、領域構成を編集し、領域詳細で 1 つの領域を解析します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="264"/>
        <source>Select a row for its summary; press Enter or double-click to open Region Detail.</source>
        <translation>行を選択して概要を確認します。Enterキーまたはダブルクリックで領域詳細を開きます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="271"/>
        <source>Selected region summary</source>
        <translation>選択した領域の概要</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="286"/>
        <source>Show all regions or limit the table to one readiness category.</source>
        <translation>すべての領域を表示するか、1つの解析状態に絞り込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="294"/>
        <source>Shows the absorption region currently open in Region Detail.</source>
        <translation>領域詳細で現在開いている吸収領域を表示します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="302"/>
        <source>Side Panel</source>
        <translation>サイドパネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="303"/>
        <source>Side panel for maintaining the tree of absorption regions and absorption lines.</source>
        <translation>領域やラインをツリービューで整理するためのサイドパネルです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="305"/>
        <source>Slide the detection threshold to rebuild the hit list.</source>
        <translation>σ閾値スライダーを操作して、吸収線領域の候補一覧を更新します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="306"/>
        <source>Specify the FITS files for the observed flux and error and load them into the project.</source>
        <translation>観測スペクトルのフラックスと誤差の FITS ファイルを指定し、プロジェクトへ読み込みます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="307"/>
        <source>Specify the Hubble constant H₀ in the range 50.0–100.0 km/s/Mpc. Step 0.1, default 67.4.</source>
        <translation>ハッブル定数 H₀ を 50.0 ～ 100.0 km/s/Mpc の範囲で指定します。ステップ 0.1、初期値 67.4。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="308"/>
        <source>Specify the ionisation stage for the selected element. Changing the element updates the available stages.</source>
        <translation>選択中の元素に対するイオン段階を指定します。元素を替えると利用可能な段階が更新されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="309"/>
        <source>Specify the path of the FITS file containing the observed error. When omitted, the data is treated as having no error.</source>
        <translation>観測誤差を含む FITS ファイルのパスを指定します。未指定の場合は誤差なしとして扱います。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="310"/>
        <source>Specify the resolution R = λ/Δλ in the range 10–100000. Up to two decimal places are accepted.</source>
        <translation>分解能 R = λ/Δλ を 10 ～ 100000 の範囲で指定します。小数点以下 2 桁まで入力できます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="311"/>
        <source>Spectrum View</source>
        <translation>スペクトル表示パネル</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="313"/>
        <source>Split selected lines into a new region.</source>
        <translation>選択したラインを新しい領域へ分割します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="315"/>
        <source>Start mode is the landing screen where you load observation data or an existing project.</source>
        <translation>スタートモードはアプリ起動直後に表示され、観測データのドラッグ＆ドロップや既存プロジェクトの読み込みを促して作業を始めます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="316"/>
        <source>Start the fit with the current configuration and update the results.</source>
        <translation>現在の設定でフィットを開始し、結果を更新します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="318"/>
        <source>Status Bar</source>
        <translation>ステータスバー</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="319"/>
        <source>Subplot selector</source>
        <translation>一時ライン取り込みチェックボックス</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="320"/>
        <source>Suggested links</source>
        <translation>連結候補</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="321"/>
        <source>Supplementary panel with mode-specific controls and information.</source>
        <translation>現在のモードに関連するコントロールや詳細情報をまとめた補助パネルです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="322"/>
        <source>Supported FITS inputs are 1D primary HDUs (with optional WCS), binary tables containing WAVELENGTH/WAVE/LAMBDA/WL and FLUX/INTENSITY/COUNTS/DATA columns, or multi-extension files with WAVELENGTH and FLUX (and optionally ERROR/ERR/SIGMA) extensions. Files whose column or extension names do not match cannot be loaded.</source>
        <translation>対応する FITS は次のいずれかです: 1 次元プライマリ HDU（WCS 対応可）、WAVELENGTH/WAVE/LAMBDA/WL と FLUX/INTENSITY/COUNTS/DATA 列を持つバイナリテーブル、拡張名 WAVELENGTH・FLUX（任意で ERROR/ERR/SIGMA）を含むマルチ拡張。列名・拡張名が一致しない場合は読み込めません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="324"/>
        <source>Switch the display language of the whole application and check the wording in the preview.</source>
        <translation>アプリケーション全体の表示言語を切り替え、プレビューで表記を確認します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="326"/>
        <source>The area that lists the selected lines. Guidance text is shown while nothing is selected.</source>
        <translation>選択済みラインの一覧を表示する領域です。未選択の間は案内テキストが表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="327"/>
        <source>The area where the selected line species are shown.</source>
        <translation>選択済みの線種が表示される領域です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="328"/>
        <source>The available presets. Selecting one updates the details and the state of the edit buttons.</source>
        <translation>利用可能なプリセット一覧。選択すると詳細や、編集ボタン等の状態が更新されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="329"/>
        <source>The confirmed regions in the side panel are the same regions that Analysis Overview lists in its region list. To delete, merge, split, or unlink one, right-click its row and choose Edit region to open Analysis Structure, then follow [Analysis Structure](../../../operations/analysis-structure.md).</source>
        <translation>サイドパネルの確定領域は、解析概要の領域一覧に並ぶ領域と同じものです。領域の削除、統合、分割、連結解除を行うには、対象の行を右クリックして［領域を編集］を選び、解析の構造編集を開きます。手順は[解析の構造編集](../../../operations/analysis-structure.md)を参照してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="330"/>
        <source>The data control panel is hidden while you stay in Start mode.</source>
        <translation>スタートモードではデータ制御パネルやスペクトルパネルが非表示です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="331"/>
        <source>The dialog only appears while the project has unsaved changes; otherwise the project closes straight away.</source>
        <translation>このダイアログは、プロジェクトに未保存の変更がある場合にのみ表示されます。変更がなければそのまま閉じます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="332"/>
        <source>The error file is optional, but providing it enables uncertainty-aware analysis.</source>
        <translation>誤差ファイルは任意ですが、指定すると不確かさを用いた解析が有効になります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="333"/>
        <source>The lookback time and comoving distance columns are hidden by default; enable them from the column header&apos;s right-click menu. Both are recalculated immediately when you apply new parameters in the Cosmology Settings dialog.</source>
        <translation>ルックバックタイムと共動距離の列は既定で非表示です。列ヘッダーの右クリックメニューから表示できます。どちらもコスモロジー設定ダイアログで新しいパラメータを適用すると即座に再計算されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="334"/>
        <source>The supported extension is .fits.</source>
        <translation>対応拡張子は .fits です。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="335"/>
        <source>The valid range is 10–100000; values outside it show an error.</source>
        <translation>有効範囲は 10 ～ 100000 で、それ以外はエラー表示となります。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="336"/>
        <source>The σ threshold slider and numeric input are always visible on one row and stay synchronized. The heading reports the current candidate count.</source>
        <translation>σしきい値のスライダーと数値入力は1行に常時表示され、相互に同期します。見出しには現在の候補件数が表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="337"/>
        <source>To change a link group&apos;s members, unlink the group and then link the intended rows again.</source>
        <translation>連結グループのメンバーを変更する場合は、グループを解除してから対象行を選び直して連結します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="338"/>
        <source>Toggle whether the subplot’s slice will be promoted into the final grouping.</source>
        <translation>各サブプロットを一時ラインとして取り込むかどうかを選択します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="339"/>
        <source>Top bar for switching modes and accessing common actions.</source>
        <translation>モードの切り替えと共通アクションをまとめた上部のバーです。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="341"/>
        <source>Undo</source>
        <translation>元に戻す</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="342"/>
        <source>Unlink linked lines</source>
        <translation>連結を解除</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="343"/>
        <source>Unlocking too many parameters can destabilise convergence; introduce changes gradually.</source>
        <translation>過度に多くのパラメータを解放すると収束が不安定になるため、段階的に調整してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="345"/>
        <source>Use Display range in the Velocity Plot to reframe all subplots without changing the analysis interval.</source>
        <oldsource>Use Display half-width in the Velocity Plot to reframe all subplots without changing the analysis interval.</oldsource>
        <translation>速度プロットの［表示範囲］を使用し、解析範囲を変えずにすべてのサブプロットの表示範囲を変更します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="346"/>
        <source>Use mouse wheel vertical scroll to zoom and horizontal scroll to pan.</source>
        <translation>マウスホイールの上下スクロールでズーム、左右スクロールでパン（横移動）ができます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="347"/>
        <source>Use the context bar to switch modes and invoke shared actions.</source>
        <translation>モードバーでモードを切り替え、共通アクションを呼び出します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="348"/>
        <source>Velocity Plot</source>
        <translation>速度プロット</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="349"/>
        <source>Velocity plot info</source>
        <translation>速度プロット情報</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="350"/>
        <source>Wavelength Range</source>
        <translation>波長範囲</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="351"/>
        <source>Wavelength range</source>
        <translation>波長範囲</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="353"/>
        <source>When checked, the instrument resolution is convolved into the analysis model. When unchecked, the value is stored but not applied.</source>
        <translation>チェックすると装置分解能を解析モデルへ畳み込みます。外すと入力値は保存されますが適用されません。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="354"/>
        <source>When dragging FITS files, select both flux and error files together so they are paired automatically.</source>
        <translation>FITS をドラッグする場合はフラックスと誤差の 2 ファイルを同時に選択してください。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="355"/>
        <source>When more than six slices are available, advance to the next subplot page.</source>
        <translation>7 件以上の候補がある場合に、次のサブプロットページへ移動します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="356"/>
        <source>When more than six slices are available, move back to the earlier subplot page.</source>
        <translation>7 件以上の候補がある場合に、前のサブプロットページへ移動します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="357"/>
        <source>When Ωm + ΩΛ exceeds 1, Ωk shows the sign of the curvature.</source>
        <translation>Ωm + ΩΛ が 1 を超える場合は Ωk に曲率の符号が表示されます。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="358"/>
        <source>Workspace for one selected region, including masks, component parameters, fitting, and export.</source>
        <translation>選択した1つの領域について、マスク、成分パラメータ、フィット、エクスポートを操作します。</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="359"/>
        <source>Zoom Area</source>
        <translation>範囲ズーム</translation>
    </message>
    <message>
        <location filename="_annotations_extraction_bridge.py" line="360"/>
        <source>chappy User Manual</source>
        <translation>chappy ユーザーマニュアル</translation>
    </message>
</context>
<context>
    <name>ManualExporter</name>
    <message>
        <location filename="../exporter.py" line="376"/>
        <location filename="../exporter.py" line="553"/>
        <source>Content coming soon.</source>
        <translation>現在準備中です。</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="383"/>
        <source>Internal identifier: {identifier}</source>
        <extracomment>{identifier} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>内部識別子: {identifier}</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="435"/>
        <source>Common UI</source>
        <translation>共通の画面要素</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="443"/>
        <source>Tab {index}</source>
        <extracomment>{index} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>タブ {index}</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="547"/>
        <source>Screen Overview</source>
        <translation>画面構成</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="86"/>
        <source>Hub for reviewing absorption region and line attributes while keeping the spectrum overlays aligned. It corresponds to callout</source>
        <translation>領域とラインの属性を一覧し、スペクトルの色帯と連動させながら管理する拠点です。ブラウズモードの画面構成（番号 2）に対応し、下記「サイドパネルの主な操作」で日常的な整理手順を確認できます。</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="960"/>
        <source>Side Panel Details</source>
        <translation>サイドパネルの詳細</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="13"/>
        <source>Parameter Adjustment Dialog</source>
        <translation>パラメータ詳細調整ダイアログ</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="14"/>
        <source>Right-click an absorber component and select &quot;Adjust Parameters...&quot; to open a dialog where you can intuitively adjust parameters with sliders and numeric inputs. Changes are applied to the model immediately. Use the &quot;Fixed&quot; checkbox for each parameter to freeze it during fitting.</source>
        <translation>吸収線コンポーネントを右クリックして「パラメータを調整…」を選択すると、スライダーと数値入力でパラメータを直感的に調整できるダイアログが開きます。変更は即時にモデルへ反映されます。各パラメータの「固定」チェックボックスをオンにすると、フィッティング時にそのパラメータを固定できます。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="19"/>
        <location filename="../panel_windows.py" line="435"/>
        <source>Velocity Plot</source>
        <translation>速度プロット</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="7"/>
        <location filename="../user_manual_manifest.py" line="353"/>
        <source>Analysis Structure</source>
        <translation>解析の構造編集</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="8"/>
        <source>Review and edit absorption region and line hierarchy while keeping spectrum overlays aligned. It corresponds to callout</source>
        <translation>スペクトルの重ね表示を対応させながら、吸収領域とラインの階層を確認、編集します。対応する吹き出し番号:</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="20"/>
        <source>In Analysis Region Detail, select a line in the side panel and press the V key, or right-click on the spectrum and choose &quot;Show Velocity Plot (V)&quot;, to compare absorption lines in velocity space. The &quot;Display range&quot; control changes the view for every subplot and page without changing the project or analysis settings. The line row&apos;s &quot;Analysis range [km/s]&quot; value independently defines the interval used for analysis. Compare several lines on the same velocity axis while adding and adjusting components to verify redshift consistency.</source>
        <translation>解析の領域詳細でサイドパネルのラインを選択してVキーを押すか、スペクトルを右クリックして［速度プロットを表示 (V)］を選択すると、吸収線を速度空間で比較できます。［表示範囲］はプロジェクトや解析設定を変更せず、すべてのサブプロットとページの表示を変更します。ライン行の［解析範囲 [km/s]］は解析に使用する区間を独立して定義します。同じ速度軸で複数のラインを比較しながら成分を追加、調整し、赤方偏移の整合性を確認します。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="24"/>
        <source>Main Operations</source>
        <translation>主な操作</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="26"/>
        <source>**Shift+Click**: Hold Shift and click on a subplot to add a new component at that velocity position.</source>
        <translation>**Shift+クリック**: サブプロット上でShiftキーを押しながらクリックすると、その速度位置に新しいコンポーネントを追加できます。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="30"/>
        <source>**Right-click Menu**: Right-click on a subplot to display the &quot;Add Component Here&quot; menu option.</source>
        <translation>**右クリックメニュー**: サブプロット上で右クリックすると「ここにコンポーネントを追加」メニューが表示されます。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="34"/>
        <source>**Drag Center Line**: Drag the component center (yellow for target line, orange for other lines) to adjust its redshift. An overlay shows the target position during the drag.</source>
        <translation>**中心線のドラッグ**: コンポーネントの中心（対象ラインは黄色、別ラインはオレンジの破線）をドラッグして赤方偏移を調整できます。ドラッグ中は移動先がオーバーレイで表示されます。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="38"/>
        <source>**Page Navigation**: When there are many lines, use the navigation buttons at the bottom to switch between pages.</source>
        <translation>**ページ切り替え**: 多数のラインがある場合は、下部のナビゲーションボタンでページを切り替えられます。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="42"/>
        <source>**Display range**: Enter a symmetric view range for all subplots and pages. This display-only control does not change line analysis ranges and is not recorded in scientific Undo.</source>
        <translation>**表示範囲**：すべてのサブプロットとページで共有する左右対称の表示範囲を入力します。この表示専用の操作はライン解析範囲を変更せず、科学操作のUndoには記録されません。</translation>
    </message>
    <message>
        <location filename="../data/section_texts.py" line="46"/>
        <source>**Fit view to analysis ranges**: Recalculate the display range from the current region&apos;s line analysis ranges.</source>
        <translation>**解析範囲に合わせる**：現在の領域のライン解析範囲から表示範囲を再計算します。</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="289"/>
        <location filename="../exporter.py" line="290"/>
        <source>Button</source>
        <translation>ボタン</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="291"/>
        <source>Tool button</source>
        <translation>ツールボタン</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="292"/>
        <source>Dropdown</source>
        <translation>ドロップダウン</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="293"/>
        <source>Text input</source>
        <translation>テキスト入力</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="294"/>
        <source>Text area</source>
        <translation>テキストエリア</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="295"/>
        <source>Rich text</source>
        <translation>リッチテキスト</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="296"/>
        <location filename="../exporter.py" line="297"/>
        <source>Numeric input</source>
        <translation>数値入力</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="298"/>
        <source>Date input</source>
        <translation>日付入力</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="299"/>
        <source>Date/time input</source>
        <translation>日時入力</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="300"/>
        <source>Checkbox</source>
        <translation>チェックボックス</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="301"/>
        <source>Radio button</source>
        <translation>ラジオボタン</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="302"/>
        <source>Scroll area</source>
        <translation>スクロール領域</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="303"/>
        <source>Tree view</source>
        <translation>ツリー表示</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="304"/>
        <source>Table view</source>
        <translation>テーブル表示</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="305"/>
        <location filename="../exporter.py" line="306"/>
        <source>List view</source>
        <translation>リスト表示</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="307"/>
        <source>Group</source>
        <translation>グループ</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="308"/>
        <source>Tab</source>
        <translation>タブ</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="309"/>
        <source>Progress bar</source>
        <translation>進捗バー</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="310"/>
        <source>Status bar</source>
        <translation>ステータスバー</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="913"/>
        <source>Related Dialogs</source>
        <translation>関連ダイアログ</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="917"/>
        <source>Absorption-line Database Search</source>
        <translation>吸収線データベース検索</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="964"/>
        <source>Review the side panel widgets in workflow order: the preset setup header, detection candidates, temporary lines with registration, and confirmed regions.</source>
        <translation>サイドパネルのウィジェットをワークフロー順（プリセットの設定ヘッダー、検出候補、一時ラインと登録、確定領域）に確認します。</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1114"/>
        <source>Key Operations</source>
        <translation>主な操作</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1128"/>
        <source>Notes &amp; Caveats</source>
        <translation>注意点</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1308"/>
        <location filename="../tutorial_guide.py" line="126"/>
        <source>No.</source>
        <translation>番号</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1309"/>
        <source>Item</source>
        <translation>項目</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1311"/>
        <source>Description</source>
        <translation>説明</translation>
    </message>
    <message>
        <location filename="../exporter.py" line="1314"/>
        <source>Shortcut</source>
        <translation>ショートカット</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="132"/>
        <source>Identify side panel</source>
        <translation>同定モードサイドパネル</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="139"/>
        <source>Keeps candidate review and region registration tools in view for the entire identify workflow.</source>
        <translation>候補設定タブと領域登録タブで、候補確認から領域化までの作業を補助します。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="172"/>
        <source>Metal doublet preset</source>
        <translation>金属二重項プリセット</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="178"/>
        <source>Lyman series preset</source>
        <translation>ライマン系列プリセット</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="269"/>
        <source>Region 1</source>
        <translation>領域1</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="306"/>
        <source>Detailed Parameter Adjustment</source>
        <translation>パラメータ詳細調整</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="313"/>
        <source>A dialog for adjusting absorber component parameters in real-time using sliders and numeric inputs.</source>
        <translation>吸収線コンポーネントのパラメータをスライダーと数値入力でリアルタイムに調整するダイアログです。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="518"/>
        <source>Velocity plot</source>
        <translation>速度プロット</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="525"/>
        <source>Displays observed data, model, and residuals in velocity space. Dashed boundaries mark the line analysis range; a text notice appears when that range extends beyond the view. Shift+click to add components, and drag centre lines to adjust redshifts.</source>
        <translation>観測データ、モデル、残差を速度空間に表示します。破線はライン解析範囲を示し、その範囲が表示外まで続く場合はメッセージが表示されます。Shift+クリックで成分を追加し、中心線をドラッグして赤方偏移を調整します。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="442"/>
        <source>A view that compares absorption lines in velocity space, with a display range independent from each line&apos;s analysis range.</source>
        <translation>ラインごとの解析範囲とは独立した表示範囲で、吸収ラインを速度空間上に比較する表示です。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="79"/>
        <location filename="../scenarios/analysis_structure.py" line="52"/>
        <source>Analysis Structure panel</source>
        <translation>解析の構造編集パネル</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="545"/>
        <source>Line name label</source>
        <translation>ライン名ラベル</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="552"/>
        <source>Shows the ion species and transition name for each subplot.</source>
        <translation>各サブプロットのイオン種と遷移名を表示します。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="568"/>
        <source>Previous page button</source>
        <translation>前ページボタン</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="575"/>
        <source>Navigate to the previous page.</source>
        <translation>前のページに移動します。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="587"/>
        <source>Page indicator</source>
        <translation>ページ表示</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="594"/>
        <source>Shows the current page number and total pages.</source>
        <translation>現在のページ番号と総ページ数を表示します。</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="608"/>
        <source>Next page button</source>
        <translation>次ページボタン</translation>
    </message>
    <message>
        <location filename="../panel_windows.py" line="615"/>
        <source>Navigate to the next page.</source>
        <translation>次のページに移動します。</translation>
    </message>
    <message>
        <location filename="../pipeline.py" line="313"/>
        <source>Representative subplot</source>
        <translation>速度プロット(サブプロット)</translation>
    </message>
    <message>
        <location filename="../pipeline.py" line="320"/>
        <source>Highlights a sample subplot. Dashed boundaries show the New-candidate analysis range, while Display range controls only the shared view range.</source>
        <translation>代表的なサブプロットを示します。破線は新規候補の解析範囲を示し、［表示範囲］は共通の表示範囲だけを変更します。</translation>
    </message>
    <message>
        <location filename="../pipeline.py" line="339"/>
        <source>Identify Mode Overview</source>
        <translation>同定モードの概要</translation>
    </message>
    <message>
        <location filename="../pipeline.py" line="345"/>
        <source>Identify Velocity Plot controls</source>
        <translation>同定の速度プロット操作</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="19"/>
        <source>Replacing the Spectral Line Database</source>
        <translation>スペクトル線データベースの差し替え</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="20"/>
        <source>Steps for putting your own line catalog CSV in place, and the columns it must carry.</source>
        <translation>独自のスペクトル線カタログ CSV を配置する手順と、CSV に必要な列を説明します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="25"/>
        <source>chappy reads a bundled spectral line catalog once at startup. To analyse with a different catalog, you save your own CSV under a fixed name and start chappy again.</source>
        <translation>chappy は起動時に同梱のスペクトル線カタログを一度だけ読み込みます。別のカタログで解析する場合は、決められた名前で独自の CSV を保存し、chappy を起動し直します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="31"/>
        <location filename="../pipeline.py" line="519"/>
        <source>Prerequisites</source>
        <translation>前提条件</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="33"/>
        <source>chappy is running and the main window can be operated.</source>
        <translation>chappy が起動しており、メインウィンドウを操作できること。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="34"/>
        <source>The line data you want to use is available as a CSV, or you plan to edit a copy of the bundled catalog.</source>
        <translation>使用したいスペクトル線データが CSV として手元にあるか、同梱カタログの複製を編集して用意すること。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="42"/>
        <source>Step</source>
        <translation>ステップ</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="43"/>
        <source>Action</source>
        <translation>操作</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="47"/>
        <source>Select [Settings] &gt; [Open Line Database Folder] (`Ctrl+D` / `⌘D`).</source>
        <translation>メニューの［設定］&gt;［スペクトル線データベースのフォルダを開く］（`Ctrl+D` / `⌘D`）を選択します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="50"/>
        <source>The folder that holds the replacement catalog opens in the file manager.</source>
        <translation>差し替え用カタログを置くフォルダがファイルマネージャーで開きます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="56"/>
        <source>Copy `spectral_database/db_file/spectral_lines.csv` from the folder where chappy is placed, then edit the copy.</source>
        <translation>chappy を配置したフォルダにある `spectral_database/db_file/spectral_lines.csv` を複製し、その複製を編集します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="61"/>
        <source>You keep the column layout of the bundled catalog, which is the surest starting point for a valid file.</source>
        <translation>同梱カタログと同じ列構成が保たれるため、正しい CSV を作る出発点として最も確実です。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="68"/>
        <source>Save the edited file into the folder from step 1 under the name `spectral_lines.csv`.</source>
        <translation>編集したファイルを `spectral_lines.csv` という名前でステップ 1 のフォルダに保存します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="73"/>
        <source>The replacement catalog sits at the fixed location.</source>
        <translation>差し替え用カタログが所定の場所に配置されます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="76"/>
        <source>Quit chappy and start it again.</source>
        <translation>chappy を終了し、もう一度起動します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="77"/>
        <source>chappy loads the replaced catalog while starting up.</source>
        <translation>起動処理の中で差し替えたカタログが読み込まれます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="83"/>
        <source>Columns of the CSV</source>
        <translation>CSV の列</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="84"/>
        <source>Column</source>
        <translation>列</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="85"/>
        <source>Requirement</source>
        <translation>条件</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="86"/>
        <source>Meaning</source>
        <translation>意味</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="88"/>
        <source>Columns every row needs</source>
        <translation>すべての行に必要な列</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="89"/>
        <source>A row becomes a usable line only when all of the following hold. A row that falls short is skipped without a message, so a mistyped column name costs you lines silently.</source>
        <translation>以下の条件をすべて満たす行だけがスペクトル線として使われます。条件を満たさない行はメッセージなしで読み飛ばされるため、列名を打ち間違えると気付かないうちにスペクトル線が欠落します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="97"/>
        <source>Identifier of the row. It must not be empty, and it must be unique in the file because presets remember lines by this value.</source>
        <translation>行の識別子。空にはできません。プリセットはこの値でスペクトル線を記憶するため、ファイル内で一意にします。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="105"/>
        <source>Rest wavelength in Å. It must be larger than 0.</source>
        <translation>静止波長［Å］。0 より大きい値にします。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="109"/>
        <source>Oscillator strength. It must be larger than 0.</source>
        <translation>振動子強度。0 より大きい値にします。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="113"/>
        <source>Natural damping constant in s⁻¹. It must be larger than 0.</source>
        <translation>自然幅［s⁻¹］。0 より大きい値にします。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="119"/>
        <source>At least one of the three, so that the species can be resolved. From element_symbol and charge_state the species is composed as `Mg II`; without them the first two words of name are used.</source>
        <translation>イオン種を決めるため、3 つのうち少なくとも 1 つが必要です。element_symbol と charge_state からは `Mg II` の形で組み立て、それらがない場合は name の先頭 2 語を使います。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="128"/>
        <source>Columns you may add</source>
        <translation>任意で追加できる列</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="129"/>
        <source>These columns can be omitted or left empty.</source>
        <translation>以下の列は省略しても、空のままにしても構いません。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="135"/>
        <source>Display name of the line, for example `Mg II 2796`.</source>
        <translation>スペクトル線の表示名。例：`Mg II 2796`。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="139"/>
        <source>Element symbol such as `C`, `Mg`, `H`.</source>
        <translation>元素記号。例：`C`、`Mg`、`H`。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="143"/>
        <source>Charge as a number, where 0 is neutral and 1 is singly ionised. An ionisation stage in Roman numerals, for example `II`, is also accepted.</source>
        <translation>電離度を数値で指定します。0 が中性、1 が一価イオンです。`II` のようなローマ数字の電離段階も受け付けます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="151"/>
        <source>Ties lines into one multiplet; every member carries the same value. The bundled catalog spells the column without the first `l`, and `multiplet_name` also works.</source>
        <translation>複数のスペクトル線を 1 つの Multiplet にまとめます。同じグループには同じ値を入れます。同梱カタログでは最初の `l` を欠いた綴りになっており、`multiplet_name` でも認識されます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="157"/>
        <source>Free note kept together with the line.</source>
        <translation>スペクトル線とともに保持される自由記述のメモ。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="159"/>
        <source>The other columns</source>
        <translation>その他の列</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="160"/>
        <source>The bundled catalog carries further NIST fields such as wavelength_ritz, Ei_eV, accuracy, and the term symbols. chappy shows them as line details and accepts them empty.</source>
        <translation>同梱カタログには wavelength_ritz、Ei_eV、accuracy、項記号といった NIST 由来の列も含まれます。chappy はこれらをスペクトル線の詳細として表示し、空でも受け付けます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="168"/>
        <source>Alternative column names are accepted as well: wavelength_angstrom for wavelength, oscillator_strength for f_value, gamma_value for gamma, comments for comment.</source>
        <translation>別名の列も受け付けます。wavelength には wavelength_angstrom、f_value には oscillator_strength、gamma には gamma_value、comment には comments が使えます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="174"/>
        <source>Comment lines at the top of the file</source>
        <translation>ファイル先頭のコメント行</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="175"/>
        <source>Empty lines and lines starting with `#` are skipped. Two of them are read as the origin of the catalog and written into exported preset files.</source>
        <translation>空行と `#` で始まる行は読み飛ばされます。そのうち次の 2 行はカタログの来歴として読み取られ、書き出したプリセットファイルに記録されます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="184"/>
        <source>&gt; [!WARNING]
&gt; When no row of the CSV can be used, chappy shows the path in an error dialog at startup and quits instead of running on an empty catalog. Save the file as UTF-8 and compare the column names against the bundled catalog.</source>
        <translation>&gt; [!WARNING]
&gt; CSV の行を 1 つも使用できない場合、chappy は空のカタログで動作せず、起動時にパスを示すエラーダイアログを表示して終了します。ファイルは UTF-8 で保存し、列名を同梱カタログと見比べてください。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="190"/>
        <source>&gt; [!NOTE]
&gt; The catalog is read only while chappy starts. A file replaced during a session takes effect at the next startup.</source>
        <translation>&gt; [!NOTE]
&gt; カタログを読み込むのは chappy の起動時だけです。使用中に差し替えたファイルは次回の起動で反映されます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="195"/>
        <source>&gt; [!TIP]
&gt; To keep the catalog in another location, set the environment variable `CHAPPY_SPECTRAL_LINES_CSV` to its full path. That path is used ahead of the folder opened in step 1.</source>
        <translation>&gt; [!TIP]
&gt; カタログを別の場所に置きたい場合は、環境変数 `CHAPPY_SPECTRAL_LINES_CSV` にそのフルパスを設定します。このパスはステップ 1 で開くフォルダより優先されます。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="41"/>
        <location filename="../pipeline.py" line="522"/>
        <source>Procedure</source>
        <translation>操作手順</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="44"/>
        <source>Expected Result</source>
        <translation>期待される結果</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="182"/>
        <location filename="../pipeline.py" line="525"/>
        <location filename="../tutorial_guide.py" line="359"/>
        <source>Tips and Best Practices</source>
        <translation>注意点とベストプラクティス</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="203"/>
        <location filename="../pipeline.py" line="528"/>
        <location filename="../tutorial_guide.py" line="369"/>
        <source>Related References</source>
        <translation>関連資料</translation>
    </message>
    <message>
        <location filename="../pipeline.py" line="562"/>
        <source>| Step | Action | Expected Result |</source>
        <translation>| ステップ | 操作 | 期待される結果 |</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="44"/>
        <location filename="../user_manual_manifest.py" line="423"/>
        <source>Guided Tutorial</source>
        <translation>ガイド付きチュートリアル</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="45"/>
        <source>What the in-app guided tour teaches, how it starts, and how to run it again from the Help menu.</source>
        <translation>アプリ内のガイドツアーで学べる内容と、開始方法、［ヘルプ］メニューからの再開方法を説明します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="51"/>
        <source>chappy includes a guided tour: coach-mark bubbles that highlight one widget at a time and walk you through the analysis workflow on the bundled sample spectrum of quasar Q0329-385. It never touches your own data, because it opens the sample spectrum itself before it starts.</source>
        <translation>chappy には、ウィジェットを 1 つずつハイライトするコーチマーク（吹き出し）で解析の流れを案内するガイドツアーがあります。同梱されたクェーサー Q0329-385 のサンプルスペクトルを使って進み、開始前にツアー自身がそのサンプルを開くため、ご自身のデータに触れることはありません。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="59"/>
        <source>Starting the Tour</source>
        <translation>ツアーを開始する</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="60"/>
        <source>The tour is offered through the same [Welcome to chappy] dialog on both occasions below.</source>
        <translation>次の 2 つの場面のどちらでも、同じ［chappy へようこそ］ダイアログからツアーを開始できます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="65"/>
        <source>On the very first launch, chappy shows the dialog automatically, once. If the bundled sample spectrum is not part of this installation, the dialog still appears but its two walkthrough buttons are disabled; you can still open your own data from [File] &gt; [Open Observation Data].</source>
        <translation>初回起動時には、このダイアログが 1 度だけ自動で表示されます。同梱のサンプルスペクトルがインストールに含まれていない場合、ダイアログは表示されますが 2 つのコースのボタンは無効になります。その場合も、［ファイル］&gt;［観測データを開く］からご自身のデータを読み込めます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="72"/>
        <source>Afterward, select [Help] &gt; [Tutorial] to reopen the same dialog at any time and start the tour again.</source>
        <translation>2 回目以降は、［ヘルプ］&gt;［チュートリアル］を選ぶと同じダイアログをいつでも開き直し、ツアーを再開できます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="78"/>
        <source>Choosing a walkthrough opens the sample spectrum (flux and error FITS pair, resolving power already set) before the first coach mark appears, replacing whatever project was open.</source>
        <translation>コースを選ぶと、最初のコーチマークが表示される前にサンプルスペクトル（フラックスと誤差の FITS ファイル 2 点。装置分解能は設定済み）が開き、それまで開いていたプロジェクトは置き換えられます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="94"/>
        <source>Dialog Button</source>
        <translation>ダイアログのボタン</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="95"/>
        <source>Coverage</source>
        <translation>学べる範囲</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="96"/>
        <location filename="../tutorial_guide.py" line="118"/>
        <source>Chapters</source>
        <translation>章</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="99"/>
        <source>[Try the Essential Workflow]</source>
        <translation>［基本の流れを体験する］</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="127"/>
        <location filename="../tutorial_guide.py" line="269"/>
        <source>Chapter</source>
        <translation>章</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="128"/>
        <source>What You Learn</source>
        <translation>学べる内容</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="132"/>
        <source>Getting Started</source>
        <translation>はじめに</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="133"/>
        <source>Navigating the loaded spectrum: wheel/keyboard zoom and pan, rectangle zoom, undo/redo, typing an exact wavelength range, [Auto Adjust], [Reset View], and where to open your own data instead.</source>
        <translation>読み込んだスペクトルの操作方法です。ホイールとキーボードによるズームと移動、範囲ズーム、元に戻す・やり直し、波長範囲の直接入力、［自動調整］、［表示をリセット］、そしてご自身のデータを開く場所を扱います。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="153"/>
        <location filename="../tutorial_guide.py" line="274"/>
        <source>Reviewing Analysis Readiness</source>
        <translation>解析状態のレビュー</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="154"/>
        <source>Selecting the confirmed region in Analysis Overview and reading its fit readiness.</source>
        <translation>確定した領域を解析概要で選び、フィットの準備状況を読み取ります。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="162"/>
        <location filename="../tutorial_guide.py" line="279"/>
        <source>Fitting a Region in Detail</source>
        <translation>領域詳細でのフィット</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="163"/>
        <source>Opening Analysis Region Detail, adding a fit component to a line, running the optimizer, and reading the fit outcome.</source>
        <translation>解析の領域詳細を開き、ラインにフィットコンポーネントを追加して最適化を実行し、フィット結果を読み取ります。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="197"/>
        <source>Building a Custom Preset</source>
        <translation>カスタムプリセットの作成</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="198"/>
        <source>Creating a named preset, adding Fe II and Mg II lines to it, linking and unlinking lines into tie groups, and choosing its reference line.</source>
        <translation>名前を付けたプリセットを作成し、Fe II と Mg II のラインを追加して、ラインのリンクグループを組んだり解除したりし、基準ラインを選びます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="207"/>
        <location filename="../tutorial_guide.py" line="284"/>
        <source>Identifying with the Velocity Plot</source>
        <translation>速度プロットで同定する</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="217"/>
        <location filename="../tutorial_guide.py" line="289"/>
        <source>Merging Regions</source>
        <translation>領域の統合</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="218"/>
        <source>Opening Analysis Structure for two regions, merging them so one region spans more than one ion species, splitting the Mg II multiplet back out, and re-merging the regions.</source>
        <translation>解析の構造編集で 2 つの領域を開き、複数のイオン種にまたがる 1 つの領域へ統合し、Mg II マルチプレットを再び分割してから、領域を再統合します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="229"/>
        <source>Building three-component models for both ions, tying their main components&apos; redshift together, running a joint fit, and fixing the saturated Mg II logN before fitting again.</source>
        <translation>両方のイオンに 3 成分モデルを構築し、主成分の赤方偏移をイオン間で共有して同時フィットを実行し、飽和した Mg II の logN を固定して再フィットします。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="240"/>
        <source>Switching to Continuum mode and running [Auto Estimate] to fit the continuum around the spectrum, adding and moving a control point, deleting a point, and undoing those edits.</source>
        <translation>連続光モードに切り替え、［自動推定］を実行してスペクトルに沿った連続光を求め、制御点の追加・移動・削除と、それらの編集の取り消しを行います。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="262"/>
        <source>Five chapters open only after earlier chapters have left the project in the state they need. When a chapter&apos;s prerequisite is unmet, the tour shows a warning bubble instead of that chapter&apos;s first step, offering [Back] to return to the previous step or [Continue anyway] to ignore the prerequisite and start that chapter from its first step.</source>
        <translation>5 つの章は、それ以前の章によってプロジェクトが必要な状態になってから開きます。前提条件が満たされていない場合、その章の最初のステップの代わりに警告の吹き出しが表示され、［戻る］で前のステップに戻るか、［このまま続行］で前提条件を無視してその章の最初のステップから開始するかを選べます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="228"/>
        <location filename="../tutorial_guide.py" line="294"/>
        <source>Tying Ions and Fitting Together</source>
        <translation>イオン間のパラメータ共有と同時フィット</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="239"/>
        <source>Correcting the Continuum</source>
        <translation>連続光の補正</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="172"/>
        <location filename="../tutorial_guide.py" line="250"/>
        <source>Saving Your Work</source>
        <translation>プロジェクトの保存</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="85"/>
        <source>Essential Walkthrough or Advanced Walkthrough</source>
        <translation>基本ウォークスルーまたは応用ウォークスルー</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="88"/>
        <source>The dialog offers two separate walkthroughs. The advanced walkthrough continues from where the essential one leaves off, with no overlap between the two. Each reopens the sample spectrum and starts independently, so you can run them in separate sessions.</source>
        <translation>ダイアログには 2 つの独立したウォークスルーがあります。応用ウォークスルーは基本ウォークスルーの続きから始まり、内容の重複はありません。どちらもサンプルスペクトルを開き直して独立に開始するため、別々のセッションで実行できます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="100"/>
        <source>The minimal loop: load data, identify one absorption line, fit it, save the project.</source>
        <translation>最小限の流れです。データを読み込み、吸収ラインを 1 本同定し、フィットして、プロジェクトを保存します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="107"/>
        <source>[Continue with Advanced Topics]</source>
        <translation>［応用編に進む］</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="108"/>
        <source>Continuing from the essentials: building a custom preset, identifying with the velocity plot, merging and splitting regions, tying ions together in a joint fit, and continuum correction.</source>
        <translation>基本編に続いて、カスタムプリセットの作成、速度プロットでの同定、領域の統合と分割、イオン間の同時フィット、連続光補正を扱います。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="119"/>
        <source>The essential and advanced walkthroughs each run their own chapters, in the order shown in the two tables below.</source>
        <translation>基本ウォークスルーと応用ウォークスルーは、それぞれ下の 2 つの表に示す順序で固有の章を実行します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="124"/>
        <source>Essential Walkthrough</source>
        <translation>基本ウォークスルー</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="125"/>
        <source>Advanced Walkthrough</source>
        <translation>応用ウォークスルー</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="143"/>
        <source>Identifying Absorption Lines</source>
        <translation>吸収ラインの同定</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="144"/>
        <source>Selecting the built-in &quot;Metal Lines&quot; preset, choosing a reference line, marking a candidate absorption line on the spectrum, and confirming it as a region.</source>
        <translation>組み込みプリセット「金属線」を選び、基準ラインを決めて、スペクトル上で吸収ラインの候補をマークし、領域として確定します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="173"/>
        <source>Saving the project, and a recap of the load, identify, review, fit, and save loop just completed.</source>
        <translation>プロジェクトを保存し、ここまでたどった「読み込み・同定・レビュー・フィット・保存」の流れを振り返ります。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="184"/>
        <source>Continuing from the Essentials</source>
        <translation>基本編からの続き</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="185"/>
        <source>That the sample spectrum has been reopened for this walkthrough, replacing whatever project was open, and what lies ahead: building a custom preset, identifying with the velocity plot, merging and splitting regions, tying redshifts together across ions, and correcting the continuum. Completing the essential walkthrough first is recommended, though not required.</source>
        <translation>このウォークスルー用にサンプルスペクトルが開き直され、開いていたプロジェクトが置き換わったことと、この先で扱う内容を説明します。カスタムプリセットの作成、速度プロットでの同定、領域の統合と分割、イオン間での赤方偏移の共有、連続光の補正を扱います。必須ではありませんが、先に基本ウォークスルーを完了することを推奨します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="208"/>
        <source>Selecting the custom preset, moving to a second, hidden absorption line in the sample, and using the velocity plot to identify and confirm it.</source>
        <translation>カスタムプリセットを選び、サンプルの中に隠れたもう 1 本の吸収ラインへ移動して、速度プロットで同定・確定します。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="251"/>
        <source>Saving the project, and a recap of the preset-building, velocity-plot identification, region-editing, cross-ion tying, and continuum-correction work just completed.</source>
        <translation>プロジェクトを保存し、完了したプリセット作成、速度プロットでの同定、領域編集、イオン間の連結、連続光補正を振り返ります。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="261"/>
        <source>Chapter Prerequisites</source>
        <translation>章の前提条件</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="270"/>
        <source>Needs</source>
        <translation>必要な状態</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="275"/>
        <location filename="../tutorial_guide.py" line="280"/>
        <source>At least one confirmed absorption region.</source>
        <translation>確定した吸収領域が 1 つ以上あること。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="285"/>
        <source>A custom preset created in an earlier chapter.</source>
        <translation>前の章で作成したカスタムプリセットがあること。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="290"/>
        <source>At least two confirmed absorption regions.</source>
        <translation>確定した吸収領域が 2 つ以上あること。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="295"/>
        <source>A region that combines two or more ion species.</source>
        <translation>2 つ以上のイオン種を含む領域があること。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="299"/>
        <source>Step Controls</source>
        <translation>ステップの操作ボタン</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="300"/>
        <source>Every coach-mark bubble carries the same controls, alongside the step&apos;s instruction and expected result.</source>
        <translation>コーチマークの吹き出しには、そのステップの操作内容と期待される結果に加えて、どれも同じ操作ボタンが並びます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="305"/>
        <source>Control</source>
        <translation>ボタン</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="306"/>
        <source>Effect</source>
        <translation>動作</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="307"/>
        <source>[{label}]</source>
        <translation>［{label}］</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="311"/>
        <source>Advances to the next step. On a step that checks for a specific action (for example, confirming a region or linking preset lines), [Next] stays disabled and the expected-result line stays unchecked until that action is performed; performing it enables [Next] without advancing automatically, so you can read the confirmation first.</source>
        <translation>次のステップへ進みます。特定の操作を確認するステップ（領域の確定やプリセットのラインのリンクなど）では、その操作を行うまで［次へ］は無効のままで、期待される結果にもチェックが付きません。操作を行うと［次へ］が有効になりますが、自動では進まないため、確認の表示を読んでから進められます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="322"/>
        <source>Returns to the previous step, or to the previous chapter&apos;s last step at a chapter&apos;s first step. It does not undo anything you did in the application.</source>
        <translation>前のステップに戻ります。章の最初のステップでは、前の章の最後のステップに戻ります。アプリケーション側で行った操作が取り消されることはありません。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="330"/>
        <source>Closes the tour immediately, keeping whatever the tour has done to the project so far.</source>
        <translation>ツアーをすぐに終了します。ツアーがそれまでにプロジェクトへ加えた変更はそのまま残ります。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="338"/>
        <source>Shown only on steps that carry background information beyond the instruction itself; expands or collapses that note in place.</source>
        <translation>操作内容だけでは分からない補足があるステップにのみ表示され、その場で補足の表示と非表示を切り替えます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="346"/>
        <source>Ending and Restarting</source>
        <translation>終了と再開</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="348"/>
        <source>&gt; [!NOTE]
&gt; The tour keeps no memory of where you stopped. Whether you close it with [Exit Tour] or quit chappy, the next walkthrough you start from [Help] &gt; [Tutorial] begins again at its own first chapter and reopens the sample spectrum. Switching modes yourself does not end the tour, but the widget the current step points at is no longer on screen; switch back to the mode the chapter is guiding to see the coach mark again.</source>
        <translation>&gt; [!NOTE]
&gt; ツアーは中断した位置を記憶しません。［ツアーを終了］で閉じた場合も、chappy を終了した場合も、次に［ヘルプ］&gt;［チュートリアル］から始めるウォークスルーは、それぞれの最初の章からやり直しになり、サンプルスペクトルも開き直されます。自分でモードを切り替えてもツアーは終了しませんが、現在のステップが指しているウィジェットは画面から消えます。その章が案内しているモードに戻すと、コーチマークが再び表示されます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="361"/>
        <source>&gt; [!TIP]
&gt; The tour targets specific widgets by name. If a step&apos;s highlighted area looks empty, the window may be too narrow to show that widget; enlarge the window or reveal the collapsed panel it belongs to.</source>
        <translation>&gt; [!TIP]
&gt; ツアーはウィジェットを名前で指し示します。ハイライトされた場所が空に見える場合は、ウィンドウが狭くてそのウィジェットが表示されていない可能性があります。ウィンドウを広げるか、そのウィジェットが含まれる折りたたまれたパネルを展開すると表示されます。</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="372"/>
        <location filename="../user_manual_manifest.py" line="88"/>
        <source>Load Data into the Application</source>
        <translation>データを読み込む</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="90"/>
        <source>Steps for importing FITS spectra or project files from any mode.</source>
        <translation>任意のモードから FITS やプロジェクトを読み込む基本手順です。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="104"/>
        <source>Identify Absorption Regions and Line Species</source>
        <translation>スペクトル上の吸収領域とスペクトル線種を紐づけ同定する</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="107"/>
        <source>Use Identify mode to link spectral regions with line species and build absorption regions and lines.</source>
        <translation>同定モードで吸収領域と線種を紐づけ、領域とラインを作成する手順です。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="122"/>
        <source>Fit absorption lines per region, run the optimizer, and deliver the final results.</source>
        <translation>領域単位で吸収線をモデリングし、最適化して結果を出力するまでの手順です。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="151"/>
        <source>Adjust the Continuum Model to Stabilize the Baseline</source>
        <translation>連続光モデルを調整してスペクトルの基準を整える</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="183"/>
        <location filename="../user_manual_manifest.py" line="186"/>
        <location filename="../user_manual_manifest.py" line="189"/>
        <location filename="../user_manual_manifest.py" line="192"/>
        <location filename="../user_manual_manifest.py" line="195"/>
        <source>Work in progress. Not available yet.</source>
        <translation>準備中です。現時点では利用できません。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="204"/>
        <source>Equivalent to the `Ctrl+A` shortcut (`⌘A` on macOS) on the spectrum view.</source>
        <translation>スペクトルビューの `Ctrl+A`（macOS では `⌘A`）ショートカットと同等です。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="223"/>
        <source>Opens the Preset Management dialog in Identify mode.</source>
        <translation>同定モードでプリセット管理ダイアログを開きます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="230"/>
        <source>This section summarises each menu&apos;s role and common shortcuts.</source>
        <translation>各メニューの役割と主なショートカットをまとめています。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="236"/>
        <source>Create, open, save, or exit a project.</source>
        <translation>プロジェクトの新規作成、読み込み、保存、終了を行います。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="239"/>
        <source>Edit operations such as undo/redo (some items are not yet available).</source>
        <translation>取り消し/やり直しなどの編集操作です（一部は準備中）。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="245"/>
        <source>Adjust spectrum display ranges and related view settings.</source>
        <translation>スペクトルの表示範囲などを調整します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="249"/>
        <source>Switch analysis modes.</source>
        <translation>解析モードを切り替えます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="252"/>
        <source>Open the manual or view application information.</source>
        <translation>マニュアルの表示やアプリ情報を確認できます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="261"/>
        <source>Chappy User Manual</source>
        <translation>Chappy ユーザーマニュアル</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="264"/>
        <source>A guide to using Chappy and understanding each screen.</source>
        <translation>Chappy の使い方と画面の見方をまとめたマニュアルです。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="271"/>
        <source>Quick Start</source>
        <translation>クイックスタート</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="346"/>
        <source>Review analysis readiness, fit results, and the next action for every region.</source>
        <translation>各領域の解析状態、フィット結果、次の操作を確認します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="356"/>
        <source>Edit the region and line hierarchy from Analysis Overview.</source>
        <translation>解析概要から領域とラインの階層を編集します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="363"/>
        <source>Analysis Region Detail</source>
        <translation>解析の領域詳細</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="366"/>
        <source>Tune parameters, masks, and fit results for one region.</source>
        <translation>1つの領域についてパラメータ、マスク、フィット結果を調整します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="395"/>
        <source>Review key items under File, Edit, View, Mode, Settings, and Help.</source>
        <translation>ファイル/編集/表示/モード/設定/ヘルプの主要項目を一覧できます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="415"/>
        <source>Review common shortcut keys at a glance.</source>
        <translation>よく使うショートカットを一覧できます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="288"/>
        <source>Supplemental Workflows</source>
        <translation>補足ワークフロー</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="120"/>
        <source>Analyze an Absorption Region</source>
        <translation>吸収領域を解析する</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="135"/>
        <source>Review and Edit Analysis Structure</source>
        <translation>解析の構造を確認、編集する</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="137"/>
        <source>Analysis Overview and Structure let you review confirmed regions and edit their line hierarchy before opening Region Detail.</source>
        <translation>解析概要と構造編集では、領域詳細を開く前に確定済み領域を確認し、ライン階層を編集できます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="198"/>
        <source>To zoom by dragging on the spectrum, turn on Zoom Area in the context bar.</source>
        <translation>スペクトル上のドラッグでズームする場合は、モードバーの［範囲ズーム］をオンにします。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="210"/>
        <source>Place `spectral_lines.csv` in this folder to replace the line database, then restart Chappy.</source>
        <translation>スペクトル線データベースを差し替えるには、このフォルダに `spectral_lines.csv` を置き、Chappy を再起動する。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="217"/>
        <source>Use before fitting in Analysis Region Detail to confirm instrument resolution.</source>
        <translation>解析の領域詳細でフィットする前に装置分解能を確認するときに使用します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="250"/>
        <source>Open settings dialogs.</source>
        <translation>設定ダイアログを開きます。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="273"/>
        <source>Step-by-step walkthrough of common operations. To switch modes, click one of the mode buttons (Identify, Analysis, Continuum) in the context bar, or select from the Mode menu.</source>
        <translation>基本的な操作を順に説明します。モードを切り替えるには、モードバーのモードボタン（同定・解析・連続光）をクリックするか、［モード］メニューから選択します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="290"/>
        <source>Optional flows to review results or apply additional adjustments after completing the essentials.</source>
        <translation>必須フローの後に状況確認や追加調整を行いたいときに参照します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="305"/>
        <source>Screen Guide</source>
        <translation>画面ガイド</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="307"/>
        <source>Annotated screenshots with the roles of buttons, menus, and panels.</source>
        <translation>各画面のスクリーンショットと、ボタン・メニュー・パネルの役割を説明します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="36"/>
        <source>A project containing regions and lines is open.</source>
        <translation>領域やラインを含むプロジェクトを開いていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="39"/>
        <source>Analysis Structure is open from Overview.</source>
        <translation>解析概要から構造編集を開いていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="43"/>
        <source>Reading the Screen</source>
        <translation>主な画面の見方</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="45"/>
        <source>Overview of Analysis Structure and its relationship to the spectrum.</source>
        <translation>解析の構造編集とスペクトルの対応を確認します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="54"/>
        <source>Lists the hierarchy of regions and lines; status badges show counts and wavelength ranges.</source>
        <translation>領域とラインの階層を一覧表示し、ステータスバッジで件数や波長範囲を把握できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="62"/>
        <source>Spectrum view</source>
        <translation>スペクトルビュー</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="84"/>
        <source>The Structure panel&apos;s right-click menu provides management operations such as rename, merge, and delete.</source>
        <translation>構造編集パネルの右クリックメニューから、名称変更、統合、削除を実行できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="105"/>
        <source>Analysis Structure Screen</source>
        <translation>解析の構造編集画面</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="113"/>
        <location filename="../user_manual_manifest.py" line="343"/>
        <source>Analysis Overview</source>
        <translation>解析概要</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="64"/>
        <source>Moves to the wavelength range of the selected region or line and overlays absorption-line profiles for checking.</source>
        <translation>選択した領域やラインの波長範囲へ移動し、吸収線プロファイルを重ねてチェックします。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="72"/>
        <source>Detail panel</source>
        <translation>詳細パネル</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="74"/>
        <source>Shows the transition list and measurements to review parameters confirmed in Identify mode.</source>
        <translation>転移リストや測定値を表示し、同定モードで確定したパラメータを確認します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="82"/>
        <source>Context menu</source>
        <translation>コンテキストメニュー</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="95"/>
        <source>Pick the management operation you need. All are optional and help you inventory and organise regions and lines.</source>
        <translation>必要な管理操作を選んで参照します。いずれも任意で、領域とラインの棚卸しや整理に役立ちます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_structure.py" line="93"/>
        <source>Task-based Operation Guide</source>
        <translation>目的別の操作ガイド</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="87"/>
        <location filename="../scenarios/analysis_structure.py" line="109"/>
        <location filename="../scenarios/continuum.py" line="61"/>
        <location filename="../scenarios/identify.py" line="55"/>
        <location filename="../scenarios/start.py" line="82"/>
        <location filename="../user_manual_manifest.py" line="314"/>
        <source>Common Screen Elements</source>
        <translation>共通の画面要素</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="317"/>
        <source>Items commonly available in the main window.</source>
        <translation>メインウィンドウで共通して利用する項目の一覧。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="25"/>
        <source>chappy is running and the main window is accessible.</source>
        <translation>chappy が起動しており、メインウィンドウにアクセスできること。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="32"/>
        <source>A FITS pair of observed flux and observed error, or a chappy project (.h5), is available.</source>
        <translation>観測フラックスと観測誤差の FITS ペア、または chappy プロジェクト (.h5) が用意されていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="41"/>
        <source>Save any edits in progress in other modes before loading new data.</source>
        <translation>他モードで編集中の内容があれば保存してから読み込み操作に進んでください。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="49"/>
        <source>File pairs named `*_f.fits` / `*_e.fits` are assigned flux and error roles automatically. For other names, reselect the observed flux and error in the dialog.</source>
        <translation>ファイル名が `*_f.fits` / `*_e.fits` のペアであれば自動でフラックスと誤差の役割が割り当てられます。別名を指定した場合はダイアログで観測フラックスと誤差を選び直してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="59"/>
        <source>Supported FITS layouts are a one-dimensional primary HDU (WCS supported), a binary table with WAVELENGTH/WAVE/LAMBDA/WL and FLUX/INTENSITY/COUNTS/DATA columns, or a multi-extension file with WAVELENGTH and FLUX extensions (optionally ERROR/ERR/SIGMA). Files whose column or extension names do not match cannot be loaded.</source>
        <translation>対応する FITS 形式は 1 次元プライマリ HDU（WCS 対応可）、WAVELENGTH/WAVE/LAMBDA/WL と FLUX/INTENSITY/COUNTS/DATA 列を持つバイナリテーブル、または拡張名 WAVELENGTH・FLUX（任意で ERROR/ERR/SIGMA）を含むマルチ拡張です。列名や拡張名が一致しないファイルは読み込めません。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="71"/>
        <source>Menus are disabled while a dialog stays open. Close the dialog first and retry.</source>
        <translation>ダイアログが開いたままの場合はメニューが無効化されます。先に該当ダイアログを閉じてから再実行してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="78"/>
        <location filename="../user_manual_manifest.py" line="323"/>
        <source>Start Mode Overview</source>
        <translation>スタートモードの画面と操作</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="91"/>
        <source>Start chappy and confirm the main window responds in any mode.</source>
        <translation>chappy を起動し、どのモードでもメインウィンドウが操作可能か確認します。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="95"/>
        <source>The File menu and drag &amp; drop are available.</source>
        <translation>ファイルメニューやドラッグ＆ドロップが利用できる状態になっています。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="99"/>
        <source>Choose &quot;File &gt; Open Observation Data…&quot; or &quot;File &gt; Open Project…&quot; from the menu, or drag &amp; drop files directly onto the start-mode drop zone or the spectrum view.</source>
        <translation>メニューの「ファイル &gt; 観測データを開く…」または「ファイル &gt; プロジェクトを開く…」を選択するか、スタートモードのドロップゾーンやスペクトルビューへ直接ファイルをドラッグ＆ドロップします。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="107"/>
        <source>A file dialog opens, or validation of the dropped files starts, and the app switches to Analysis Overview for the new data.</source>
        <translation>ファイル選択ダイアログが開くか、ドロップしたファイルの検証が始まり、新しいデータの解析概要へ切り替わります。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="140"/>
        <source>The spectrum and Analysis Overview update with the new project, and the status bar shows a completion message.</source>
        <translation>スペクトルと解析概要が新しいプロジェクトで更新され、ステータスバーに完了メッセージが表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="116"/>
        <source>When you specified observed-flux and observed-error FITS files, review the assignment in the preview, swap the flux and error roles if needed, and finish loading. A project (.h5) opens as is.</source>
        <translation>観測フラックスと観測誤差の FITS を指定した場合は、プレビューで割り当てを確認し、必要に応じてフラックスと誤差の役割を入れ替えて読み込みを完了します。プロジェクト (.h5) を選んだ場合はそのまま開きます。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="124"/>
        <source>The automatically detected pair is shown with radio buttons and can be swapped if wrong. Pressing OK continues loading.</source>
        <translation>自動認識されたペアがラジオボタンで表示され、問題があれば差し替えられます。OK を押すと読み込みが進みます。</translation>
    </message>
    <message>
        <location filename="../scenarios/start.py" line="133"/>
        <source>After loading completes, focus the spectrum view and confirm the observed flux, error, and project structure look as expected.</source>
        <translation>ロード完了後にスペクトルビューへフォーカスし、観測フラックス・誤差やプロジェクト構成が期待どおりか確認します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="326"/>
        <source>Initial layout and primary actions shown before loading data. data.</source>
        <translation>起動直後に表示されるスタート画面の構成と主要な操作導線。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="23"/>
        <source>Identify mode is active.</source>
        <translation>同定モードに切り替わっていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="26"/>
        <source>High-S/N spectra can produce so many detection candidates that interaction slows down. Adjust the detection threshold.</source>
        <translation>S/Nが高い場合、検出候補が多くなりすぎて操作が重くなることがあります。しきい値を調整してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="35"/>
        <source>The temporary line list is sorted by ascending redshift.</source>
        <translation>一時ライン一覧は赤方偏移の昇順で表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="42"/>
        <source>Candidates whose ranges overlap a confirmed region show the Registered status, so the candidate table doubles as a to-do list of unassigned features.</source>
        <translation>確定領域と範囲が重なる候補には「登録済み」の状態が表示されるため、検出候補一覧は未対応の吸収を確認する作業リストとして使えます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="51"/>
        <location filename="../user_manual_manifest.py" line="333"/>
        <source>Identify Mode Screen</source>
        <translation>同定モードの画面と操作</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="59"/>
        <source>Adding Spectral Lines to a Preset</source>
        <translation>プリセットへのスペクトル線の追加</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="65"/>
        <source>Choose an absorption-line preset with the Preset selector in the setup header at the top of the Identify side panel.</source>
        <translation>同定サイドパネル上部の設定ヘッダーにある［プリセット選択］で、吸収線プリセットを選択します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="72"/>
        <source>The Reference line selector, the candidate list, and the velocity plot update to match the selected preset. The setup header stays visible at all times, so the active preset and reference line are always in view.</source>
        <translation>基準線選択、検出候補一覧、速度プロットが選択したプリセットに合わせて更新されます。設定ヘッダーは常に表示され、使用中のプリセットと基準線をいつでも確認できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="93"/>
        <source>The added species appears in the Reference line selector&apos;s popup, and linked lines share the same Link label in the dialog. Built-in presets cannot be modified, so copy one or create a new preset when needed.</source>
        <translation>追加した線種が基準線選択のポップアップに表示され、連結したラインにはダイアログ内で同じ連結ラベルが表示されます。組み込みプリセットは変更できないため、複製するか新規プリセットを作成してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="104"/>
        <source>Select the species to use as the identification anchor with the Reference line selector in the setup header. The popup lists every line in the preset.</source>
        <translation>設定ヘッダーの［基準線選択］で、同定の基準にする線種を選択します。ポップアップにはプリセットの全ラインが一覧表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="115"/>
        <source>To change the scientific interval for upcoming candidates, set New-candidate range on the second row of the setup header.</source>
        <translation>これから追加する候補の科学的な範囲を変更するときは、設定ヘッダー2行目の［新規候補の範囲］を設定します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="122"/>
        <source>The value is used by the next Shift preview and by candidates added afterward. Existing temporary lines, registration grouping, and the Velocity Plot view range do not change.</source>
        <translation>設定値は次のShiftプレビューと、これから追加する候補に使用されます。既存の一時ライン、登録時の束ね結果、速度プロットの表示範囲は変更されません。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="132"/>
        <source>Review the detection candidate table. The σ threshold slider and numeric input are always visible on one row and stay synchronized. Each row shows the wavelength range, σ score, and status: Unassigned, Tentative, or Registered.</source>
        <translation>検出候補一覧を確認します。σしきい値のスライダーと数値入力は1行に常時表示され、相互に同期します。各行に波長範囲、σ値、状態（未対応・仮対応・登録済み）が表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="141"/>
        <source>Lowering the σ threshold adds weaker candidates to the table; the section heading reports the current count.</source>
        <translation>σ閾値を下げると弱い候補が一覧に追加されます。セクション見出しに現在の件数が表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="173"/>
        <source>The preview range is drawn according to New-candidate range, and candidate positions of the other preset species are overlaid. The spectrum also reports the current range and shows V: Verify in Velocity Plot while this Shift preview is active.</source>
        <translation>［新規候補の範囲］に従ってプレビュー範囲が描画され、プリセットに含まれる他の線種の候補位置が重ねて表示されます。このShiftプレビュー中、スペクトルには現在の範囲と［V: 速度プロットで確認］が表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="184"/>
        <source>(Identifying on the spectrum) When the preview sits at the intended position, Shift-click the spectrum view to add it as a temporary line.</source>
        <translation>（通常のスペクトルでの同定）プレビューが意図した位置になったら、スペクトルビューをShift+クリックして一時ラインを追加します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="191"/>
        <source>A new row is added to the Temporary Lines section of the side panel and the preview colours update to the matching species. When the anchor line belongs to a link group in the active preset, a temporary line is created for every line in that group.</source>
        <translation>サイドパネルの「一時ライン」セクションに新しい行が追加され、プレビューの色が対応する線種に更新されます。基準線が使用中プリセットの連結グループに属する場合は、グループ内の各ラインに一時ラインが作成されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="203"/>
        <source>(Identifying on the velocity plot) Place the cursor over the intended absorption region and press V. Hold Shift beforehand when you want to confirm the all-species preview first.</source>
        <translation>（速度プロットでの同定）意図した吸収領域にカーソルを合わせてVを押します。先に全線種プレビューを確認したいときは、あらかじめShiftを押しておきます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="211"/>
        <source>The velocity plot opens immediately at the exact cursor wavelength, whether or not the Shift preview is visible. Dashed boundaries show New-candidate range. Display range initially includes those boundaries with margin; six preset species are shown per page, with arrow buttons for later pages.</source>
        <translation>Shiftプレビューの有無にかかわらず、速度プロットがカーソル位置の波長で開きます。破線は［新規候補の範囲］を示します。初期の［表示範囲］には破線が余白付きで収まり、1ページにプリセットの線種が6つ表示されます。後続ページへは矢印ボタンで移動します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="223"/>
        <source>On the Velocity Plot, edit Display range to reframe every subplot and page. Press Fit view to analysis ranges to restore a view derived from New-candidate range.</source>
        <translation>速度プロットの［表示範囲］を編集して、すべてのサブプロットとページを表示し直します。［解析範囲に合わせる］を押すと、［新規候補の範囲］から導出した表示に戻ります。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="231"/>
        <source>Only the Velocity Plot view changes. New-candidate range, existing temporary lines, registration grouping, and scientific Undo history remain unchanged.</source>
        <translation>速度プロットの表示だけが変わります。新規候補の範囲、既存の一時ライン、登録時の束ね結果、科学操作のUndo履歴は変更されません。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="241"/>
        <source>(Identifying on the velocity plot) Click the top-left corner of the velocity plot for each species you want to identify to check it, then press Add selected lines to temporary list.</source>
        <translation>（速度プロットでの同定）同定したい各線種の速度プロット左上を選択してチェックを付け、［選択した線を一時ラインに追加］を押します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="249"/>
        <source>A blue check mark selects each species, and temporary lines for the checked species are added to the Temporary Lines section. Their ranges use New-candidate range, not Display range.</source>
        <translation>青いチェックマークで線種が選択され、チェックした線種の一時ラインが［一時ライン］セクションに追加されます。追加範囲には［表示範囲］ではなく［新規候補の範囲］が使用されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="259"/>
        <source>Review the grouping shown in the Temporary Lines section. Each group heading tells you where the lines will go on registration: a new region, or an existing region named in the heading.</source>
        <translation>「一時ライン」セクションに表示される束ね結果を確認します。各グループ見出しには、登録時にラインが新規領域になるか、見出しに示された既存領域へ追加されるかが表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="268"/>
        <source>The grouping is re-evaluated whenever temporary lines are added or removed. A warning mark on a heading means the lines overlap multiple existing regions; check the assignment in Analysis Structure after registering.</source>
        <translation>一時ラインが追加、削除されるたびにグループ分けが再評価されます。見出しの警告マークはラインが複数の既存領域と重なることを示します。登録後に解析の構造編集で所属を確認してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="279"/>
        <source>Press Register all (N groups) to save every temporary group to the project. To register only some groups, select their rows first; the button changes to Register selected (N groups).</source>
        <translation>［すべて登録 (N組)］を押すと全一時グループがプロジェクトへ保存されます。一部の組だけを登録する場合は先に対象行を選択します。ボタンが［選択を登録 (N組)］へ変わります。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="287"/>
        <source>The lines are saved immediately: they leave the temporary list, appear under Confirmed Regions, and the status bar reports the created or extended regions. Undo (Ctrl+Z, ⌘Z on macOS) reverts the registration. Lines created from the same link group remain linked in the project.</source>
        <translation>ラインは即座に保存されます。一時ライン一覧から消えて「確定領域」に表示され、作成・追加された領域がステータスバーに表示されます。元に戻す（Ctrl+Z、macOS では ⌘Z）で登録を取り消せます。同じ連結グループから作成されたラインは、プロジェクト内でも連結されたままになります。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="83"/>
        <source>If the spectral line species you want to detect is not in the preset, open the [Preset Management dialog](../menus/main_window/dialogs/PresetListDialog.md) with the Manage button and add the line to the preset in use. Link lines that should be identified and fitted together.</source>
        <translation>同定したい線種がプリセットに含まれていない場合は、［管理］から[プリセット管理ダイアログ](../menus/main_window/dialogs/PresetListDialog.md)を開き、使用中のプリセットへラインを追加します。同定とフィットで一緒に扱うラインは連結してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="111"/>
        <source>The anchor line is updated.</source>
        <translation>基準線が更新されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="150"/>
        <source>Search for absorption lines by zooming with the Up/Down keys, panning with the Left/Right keys, or double-clicking a candidate row (pressing Enter on the selected row works the same way).</source>
        <translation>上下キーでのズーム、左右キーでのパン、または候補行のダブルクリック（選択した行でEnterキーを押しても同様）で吸収線を探します。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="158"/>
        <source>These operations bring the absorption region into view.</source>
        <translation>操作により画面に吸収領域を収めます。</translation>
    </message>
    <message>
        <location filename="../scenarios/identify.py" line="165"/>
        <source>Hold Shift and place the cursor over an absorption region in the spectrum view to preview the anchor line and the candidate positions of the other preset lines.</source>
        <translation>Shift キーを押しながらスペクトルビュー上の吸収領域にカーソルを置き、基準線とプリセット中のスペクトル線の候補位置をプレビューします。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="336"/>
        <source>Candidate table and velocity plot used in identification.</source>
        <translation>同定モード特有の候補テーブルや速度プロット。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="373"/>
        <source>Continuum Mode Screen</source>
        <translation>連続光モードの画面と操作</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="376"/>
        <source>Controls for editing the continuum.</source>
        <translation>連続光編集用の操作群。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="156"/>
        <source>Work in Continuum mode to adjust control points, review the interpolation, and stabilise the spectrum’s baseline. This step is normally unnecessary for already-normalized spectra; use it when fit residuals reveal a continuum error.</source>
        <translation>連続光モードで制御点を調整し、補間結果を確認しながらスペクトルの基準線を整える流れです。規格化済みスペクトルでは通常不要です。フィット残差に連続光起因のずれが見える場合に使用します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="384"/>
        <source>Menu Guide</source>
        <translation>メニューガイド</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="386"/>
        <source>Explanation of the top menus and shortcuts.</source>
        <translation>アプリ上部のメニューとショートカットを説明します。</translation>
    </message>
    <message>
        <location filename="../line_database_guide.py" line="204"/>
        <location filename="../scenarios/start.py" line="86"/>
        <location filename="../tutorial_guide.py" line="370"/>
        <location filename="../user_manual_manifest.py" line="392"/>
        <source>Menu List</source>
        <translation>メニュー一覧</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="404"/>
        <source>Shortcuts</source>
        <translation>ショートカット</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="406"/>
        <source>Quick reference of frequently used shortcuts.</source>
        <translation>よく使うショートカットの早見表です。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="412"/>
        <source>Shortcut List</source>
        <translation>ショートカット一覧</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="425"/>
        <source>The in-app guided tour: what it teaches and how to run it again.</source>
        <translation>アプリ内のガイドツアーで学べる内容と、再開する方法を説明します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="439"/>
        <source>Data Files</source>
        <translation>データファイル</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="441"/>
        <source>Reference for the data files chappy reads when it starts.</source>
        <translation>chappy が起動時に読み込むデータファイルのリファレンスです。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="455"/>
        <source>Troubleshooting</source>
        <translation>困ったときは</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="457"/>
        <source>Checks and tips when something goes wrong.</source>
        <translation>トラブルが起きたときの確認ポイントをまとめています。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="464"/>
        <source>Troubleshooting (Work in Progress)</source>
        <translation>トラブルシューティング（準備中）</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="470"/>
        <source>Please refer to the interim troubleshooting notes.</source>
        <translation>現在整備中のトラブルシューティングをご覧ください。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="479"/>
        <source>Glossary</source>
        <translation>用語集</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="481"/>
        <source>Terms grouped by category (Data/Save, View/Check, Continuum, Identification, Analysis, Analysis Unit, Settings). Listed in Japanese and English.</source>
        <translation>用語をカテゴリ別（データ/保存、表示/確認、連続光、同定、解析、解析単位、設定）にまとめました。日本語/英語で表記します。</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="488"/>
        <source>Glossary (English)</source>
        <translation>用語集（日本語）</translation>
    </message>
    <message>
        <location filename="../user_manual_manifest.py" line="495"/>
        <source>Category-sorted glossary (English).</source>
        <translation>カテゴリ別に並んだ用語集（日本語）。</translation>
    </message>
    <message>
        <location filename="../data/analysis_structure_operations.py" line="47"/>
        <source>Side panel essentials</source>
        <translation>サイドパネルの主な操作</translation>
    </message>
    <message>
        <location filename="../data/analysis_structure_operations.py" line="51"/>
        <source>Everyday actions for organising absorption regions (regions) and absorption lines (lines).</source>
        <translation>領域とラインを整理するときによく使う操作です。</translation>
    </message>
    <message>
        <location filename="../data/analysis_structure_operations.py" line="57"/>
        <source>| Action | Steps | Notes |</source>
        <translation>| 操作 | 手順 | 補足 |</translation>
    </message>
    <message>
        <location filename="../data/analysis_structure_operations.py" line="60"/>
        <source>|---|---|---|</source>
        <translation>|---|---|---|</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="39"/>
        <source>| ↑/↓ | Zoom in/out |</source>
        <translation>| ↑/↓ | ズームイン/アウト |</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="40"/>
        <source>| ←/→ | Pan left/right |</source>
        <translation>| ←/→ | 左右にパン |</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="42"/>
        <source>| Escape | Cancel operation |</source>
        <translation>| Escape | 操作キャンセル |</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="95"/>
        <source>Keyboard &amp; Mouse Operations</source>
        <translation>キーボード・マウス操作</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="98"/>
        <source>| Operation | Description |</source>
        <translation>| 操作 | 説明 |</translation>
    </message>
    <message>
        <location filename="../data/keyboard_operations.py" line="101"/>
        <source>|------|------|</source>
        <translation>|------|------|</translation>
    </message>
    <message>
        <location filename="../single_page.py" line="31"/>
        <source>Contents</source>
        <translation>目次</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="25"/>
        <source>Observation data is loaded and Continuum mode is active.</source>
        <translation>観測データがロードされ、連続光モードへ切り替わっていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="32"/>
        <source>Permission to edit the continuum model (the project is writable).</source>
        <translation>連続光モデルを編集できる権限（プロジェクトが書き込み可能であること）。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="40"/>
        <source>Auto estimate overwrites the existing control points; back them up first (for example as CSV) if needed.</source>
        <translation>自動推定は既存の制御点を上書きするため、必要なら CSV などで事前にバックアップを取ってください。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="49"/>
        <source>After fine-tuning control points, inspect details with wavelength and flux ranges to keep the model accurate.</source>
        <translation>制御点を微調整した後は、波長範囲とフラックス範囲で詳細を確認し、モデルの精度を保ちます。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="57"/>
        <source>Continuum Mode Screen Layout</source>
        <translation>連続光モードの画面構成</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="67"/>
        <source>Open Continuum mode and run &quot;Auto Estimate&quot; from the quick actions card.</source>
        <translation>連続光モードを開き、クイック操作カードの「自動推定」を実行します。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="73"/>
        <source>The continuum curve in the spectrum view and the control point list update with the estimate.</source>
        <translation>スペクトルビューの連続光曲線と制御点リストが推定結果で更新されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="82"/>
        <source>Add control points at the wavelengths you need and drag them to adjust the flux values.</source>
        <translation>必要な波長に制御点を追加し、ドラッグしてフラックス値を調整します。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="89"/>
        <source>Added control points are reflected in the spectrum view immediately and appended to the list.</source>
        <translation>追加した制御点が即座にスペクトルビューへ反映され、リストにも追記されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="98"/>
        <source>Select control points you no longer need in the list and delete them.</source>
        <translation>不要になった制御点をリストから選択し、削除操作を実行します。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="104"/>
        <source>The control points are removed and the continuum curve is recalculated.</source>
        <translation>該当制御点が削除され、連続光曲線が再計算されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="112"/>
        <source>Finally, confirm the reset procedures with `Clear Control Points` or another `Auto Estimate`.</source>
        <translation>仕上げに `制御点をクリア` や再度の `自動推定` でリセット手順を確認します。</translation>
    </message>
    <message>
        <location filename="../scenarios/continuum.py" line="119"/>
        <source>The control point list becomes empty or is replaced by the new estimate, showing how to return to a known state.</source>
        <translation>制御点リストが空、または再推定結果に置き換わり、元の状態への戻し方を把握できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="24"/>
        <source>Regions have been created in Identify mode.</source>
        <translation>同定モードで領域を作成していること。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="35"/>
        <source>A region showing the needs-optimization badge requires re-analysis, for example after continuum model changes or manual component edits.</source>
        <translation>要最適化バッジが表示されている領域は、連続光モデルの変更や吸収線コンポーネントの手動変更等で再度解析が必要であることを示しています。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="44"/>
        <source>To exclude wavelength ranges from the analysis, set masks in the exclusion regions.</source>
        <translation>解析から除外したい波長領域がある場合は、除外領域でマスクを設定してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="53"/>
        <source>Each absorption line has an &quot;Analysis range [km/s]&quot; value that defines its analysis interval. The Velocity Plot&apos;s &quot;Display range&quot; changes only the view and is not recorded in scientific Undo.</source>
        <translation>各吸収ラインには、解析に使用する区間を定義する［解析範囲 [km/s]］があります。速度プロットの［表示範囲］は表示だけを変更し、科学操作のUndoには記録されません。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="64"/>
        <source>Selecting multiple components and choosing delete from the context menu removes all selected components at once.</source>
        <translation>複数のコンポーネントを選択して右クリックメニューから削除すると、選択したすべてのコンポーネントを一括で削除できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="73"/>
        <source>&quot;Share z&quot; and &quot;Share all parameters&quot; require two or more components that are not already in a shared group; a component already in a shared group must use &quot;Remove from shared group&quot; first before it can be regrouped.</source>
        <translation>［z を共有］［全パラメータを共有］は、いずれの共有グループにも属していないコンポーネントを2つ以上選択している場合のみ選択できます。既に共有グループに属しているコンポーネントを別のグループに再編成したい場合は、先に［共有を解除］を実行してください。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="93"/>
        <source>Select the region to analyse in the side panel.</source>
        <translation>サイドパネルで解析対象とする領域を選択します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="105"/>
        <source>Use the side panel&apos;s exclusion-region settings to exclude unwanted wavelength ranges from the optimization.</source>
        <translation>サイドパネルの除外領域設定から、不要な波長領域を最適化の対象から除外します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="112"/>
        <source>The region list updates and the exclusion regions are reflected on the spectrum.</source>
        <translation>領域の一覧が更新され、スペクトルにも除外領域が反映されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="135"/>
        <source>Add a component by clicking the add-component button, right-clicking the selected line&apos;s region on the spectrum, or Shift+clicking it.</source>
        <translation>コンポーネント追加ボタンのクリック/選択済みのラインの領域をスペクトル上での右クリック/Shift+クリックの何れかの操作でコンポーネントを追加します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="142"/>
        <source>Click-added components appear at the clicked position; button-added ones appear at the line centre. A component row is added under the selected line in the parameter table.</source>
        <translation>クリックで追加した場合はその位置に、ボタンで追加した場合はラインの中心にコンポーネントが追加されます。パラメータテーブルの選択済みのラインにコンポーネントの行が追加されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="152"/>
        <source>To adjust components while comparing several lines in velocity space, right-click the spectrum with a line selected and choose &quot;Show Velocity Plot&quot;.</source>
        <translation>複数のラインを速度空間で比較しながらコンポーネントを調整したい場合は、ラインを選択した状態でスペクトル上を右クリックし「速度プロットを表示」を選択します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="160"/>
        <source>The velocity plot window opens, where you can add components with Shift+Click and adjust the redshift by dragging the centre line.</source>
        <translation>速度プロットウィンドウが開き、Shift+クリックでのコンポーネント追加や中心線のドラッグによる赤方偏移調整が行えます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="169"/>
        <source>Edit &quot;Analysis range [km/s]&quot; on a line or multiplet row to change the interval used for analysis.</source>
        <translation>ラインまたは多重線行の［解析範囲 [km/s]］を編集し、解析に使用する範囲を変更します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="186"/>
        <source>In the Velocity Plot, edit &quot;Display range&quot; to reframe every subplot, or choose &quot;Fit view to analysis ranges&quot; to derive the view from the current region.</source>
        <translation>速度プロットで［表示範囲］を編集してすべてのサブプロットの表示範囲を変更するか、［解析範囲に合わせる］を選択して現在の領域から表示範囲を導出します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="127"/>
        <source>The selected line is highlighted and the add-component button is enabled.</source>
        <translation>選択したラインが強調表示され、成分追加ボタンが有効になります。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="28"/>
        <source>Analysis Region Detail is open for a target region.</source>
        <translation>対象領域の解析の領域詳細を開いていること。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="83"/>
        <source>Analysis Region Detail Screen</source>
        <translation>解析の領域詳細画面</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="96"/>
        <source>The spectrum view moves to fit the region, and the side panel and the parameter table in the bottom pane update to the selected region.</source>
        <translation>領域が収まる範囲にスペクトルの表示が移動し、サイドパネルと下部ペインのパラメータテーブルが選択した領域の内容に更新されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="120"/>
        <source>In the parameter table in the bottom pane, select the line to which you want to add absorption components.</source>
        <translation>下部ペインのパラメータテーブルで、吸収線コンポーネントを追加したいラインを選択します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="176"/>
        <source>The analysis interval updates for the affected linked lines and the region is marked for re-analysis. If the requested interval would exclude a model centre, the applied minimum and reason are shown.</source>
        <translation>影響する連結ラインの解析範囲が更新され、領域は再解析が必要な状態になります。要求した範囲からモデル中心が外れる場合は、適用された最小値と理由が表示されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="194"/>
        <source>Every subplot and page uses the same symmetric display range. The project, analysis intervals, and scientific Undo history remain unchanged.</source>
        <translation>すべてのサブプロットとページで同じ対称表示範囲が使用されます。プロジェクト、解析範囲、科学的なUndo履歴は変更されません。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="203"/>
        <source>To change parameters manually, drag the component&apos;s centre dashed line (yellow for the target line, orange for other lines; redshift z only), or click and edit the component&apos;s parameter cells (z, logN, b, Cf).</source>
        <translation>パラメータを手動で変更したい場合は、吸収線コンポーネントの中心の破線（対象ラインは黄色、別ラインはオレンジ）をドラッグ（z赤方偏移のみ）/吸収線コンポーネントのパラメータ(z,logN,b,Cf)のセルをクリックし編集して調整します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="212"/>
        <source>Dragging moves the component to the drop position and updates the redshift value in the parameter table; editing a cell reshapes the component after the change.</source>
        <translation>ドラッグした場合はドロップ先にコンポーネントが移動してパラメータテーブルの赤方偏移の数値が更新され、セルを編集した場合は編集後にコンポーネントの形状が変化します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="275"/>
        <source>Press Run fit to fit the current region.</source>
        <translation>［フィットを実行］を押して現在の領域をフィットします。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="222"/>
        <source>For fine slider-based adjustment, right-click the component row and choose &quot;Adjust Parameters…&quot; to open the parameter adjustment dialog.</source>
        <translation>スライダーで細かく調整したい場合は、吸収線コンポーネントの行を右クリックし「パラメータを調整…」を選択してパラメータ詳細調整ダイアログを開きます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="229"/>
        <source>The dialog lets you adjust each parameter (logN, b, z, Cf) intuitively with sliders and numeric input; changes are applied to the model immediately.</source>
        <translation>ダイアログが開き、各パラメータ（logN、b、z、Cf）をスライダーと数値入力で直感的に調整でき、変更は即時にモデルへ反映されます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="239"/>
        <source>Right-click a component row to toggle parameter fixing as needed. Select multiple components with Ctrl+Click (⌘+Click on macOS) or Shift+Click to toggle fixing in bulk. The &quot;Fixed&quot; checkbox in the parameter adjustment dialog also toggles it (single selection only).</source>
        <translation>必要に応じて追加した吸収線コンポーネントの行を右クリックし、パラメータの固定/解放を切り替えます。Ctrl+クリック（macOS では ⌘+クリック）や Shift+クリックで複数のコンポーネントを選択すると、一括で固定/解放を切り替えられます。パラメータ詳細調整ダイアログ内の「固定」チェックボックスからも切り替えられます（単一選択時のみ）。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="248"/>
        <source>Cells of fixed parameters change colour in the table.</source>
        <translation>固定されたパラメータ表のセルの色が変わります。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="255"/>
        <source>To fit several components together, select two or more components and right-click to choose &quot;Share z&quot; (redshift only) or &quot;Share all parameters&quot; (z, b, logN, Cf; requires the same ion). Choose &quot;Remove from shared group&quot; to detach the selected components again.</source>
        <translation>複数のコンポーネントを連動させて調整したい場合は、対象のコンポーネントを2つ以上選択し、右クリックメニューから［z を共有］（赤方偏移のみ）または［全パラメータを共有］（z、b、logN、Cf。同一イオンのコンポーネント同士のみ）を選択します。共有をやめて個別に調整したい場合は［共有を解除］を選択します。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="264"/>
        <source>Shared parameter cells show a bracketed label such as [A] before the value, and editing one shared cell updates every component in the group. If the selected components&apos; redshifts differ, a confirmation dialog appears before aligning them; each action can be undone with Ctrl+Z (⌘Z on macOS).</source>
        <translation>共有されたパラメータのセルには数値の前に［A］のような英字ラベルが表示され、どれか1つのセルを編集するとグループ内のすべてのコンポーネントに反映されます。選択したコンポーネント間で赤方偏移が異なる場合は、値をそろえる前に確認ダイアログが表示されます。いずれの操作も Ctrl+Z（macOS では ⌘Z）で元に戻せます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="277"/>
        <source>The model (red) and residual (yellow) on the spectrum change according to the fit result.</source>
        <translation>フィット結果に応じてスペクトル上のモデル（赤）と残差（黄）が変わります。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="286"/>
        <source>Use Export Results to save the analysis results as CSV.</source>
        <translation>結果の書き出し で解析結果を CSV で保存できます。</translation>
    </message>
    <message>
        <location filename="../scenarios/analysis_detail.py" line="291"/>
        <source>When the save dialog completes, the file is created at the chosen path. On Windows you can choose the encoding (UTF-8 BOM / UTF-8); pick UTF-8 BOM if characters such as Å appear garbled in Excel.</source>
        <translation>保存ダイアログが完了すると、指定したパスにファイルが作成されます。Windows では保存時にエンコーディング（UTF-8 BOM / UTF-8）を選択でき、Excel でÅ記号などが文字化けする場合は UTF-8 BOM を選択してください。</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="78"/>
        <source>Linked metal lines example</source>
        <translation>連結した金属ラインの例</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="122"/>
        <source>Loading Observation Data</source>
        <translation>観測データの読み込み</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="126"/>
        <source>Closing a Project</source>
        <translation>プロジェクトを閉じる</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="131"/>
        <source>Instrument Resolution Settings</source>
        <translation>観測装置分解能設定</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="135"/>
        <source>Cosmology Parameter Settings</source>
        <translation>宇宙論パラメータ設定</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="139"/>
        <source>Language Settings</source>
        <translation>言語設定</translation>
    </message>
    <message>
        <location filename="../dialog_providers.py" line="143"/>
        <source>Preset Management</source>
        <translation>プリセット管理</translation>
    </message>
</context>
<context>
    <name>ManualMenu</name>
    <message>
        <location filename="../menu_exporter.py" line="180"/>
        <source>Action</source>
        <translation>操作</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="184"/>
        <source>Shortcut</source>
        <translation>ショートカット</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="189"/>
        <source>Available Modes</source>
        <translation>使えるモード</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="194"/>
        <source>Description</source>
        <translation>説明</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="245"/>
        <source>See [{label}]({path}) for details of the dialog.</source>
        <extracomment>{label} と {path} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>ダイアログの詳細は [{label}]({path}) を参照してください。</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="258"/>
        <location filename="../menu_exporter.py" line="419"/>
        <location filename="../menu_exporter.py" line="422"/>
        <source>All modes</source>
        <translation>すべてのモード</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="284"/>
        <source>This page explains the actions and shortcuts for the {menu} menu.</source>
        <extracomment>{menu} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>このページでは、{menu}の操作とショートカットを説明します。</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="297"/>
        <location filename="../menu_exporter.py" line="567"/>
        <source>Menu Structure</source>
        <translation>メニューの構成</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="451"/>
        <source>Menu Overview</source>
        <translation>メニュー概要</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="460"/>
        <source>This is the legacy format. Please use [Menus (Single Page)]({name}) instead.</source>
        <extracomment>{name} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>このページは従来形式です。現在は[メニュー一覧]({name})をご利用ください。</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="499"/>
        <source>Shortcuts</source>
        <translation>ショートカット</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="502"/>
        <source>| Action | Shortcut |</source>
        <translation>| 操作 | ショートカット |</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="520"/>
        <source>Menus</source>
        <translation>メニュー一覧</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="526"/>
        <source>This single page summarises all top menus. Use the table of contents below to jump to a menu.</source>
        <translation>このページでは、アプリ上部の各メニューをまとめて説明します。以下の目次から見たいメニューへ移動できます。</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="535"/>
        <source>&gt; Profile: {slug}</source>
        <extracomment>{slug} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>&gt; プロファイル: {slug}</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="542"/>
        <source>Table of Contents</source>
        <translation>目次</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="578"/>
        <source>Actions</source>
        <translation>操作一覧</translation>
    </message>
    <message>
        <location filename="../menu_exporter.py" line="305"/>
        <location filename="../menu_exporter.py" line="588"/>
        <source>Dialogs Opened from This Menu</source>
        <translation>このメニューから開くダイアログ</translation>
    </message>
</context>
<context>
    <name>ManualTemplates</name>
    <message>
        <location filename="../templates.py" line="43"/>
        <source>Target version: {version}</source>
        <extracomment>{version} は実行時に置換されるため書き換えないこと。</extracomment>
        <translation>対象バージョン: {version}</translation>
    </message>
    <message>
        <location filename="../templates.py" line="44"/>
        <source>Start</source>
        <translation>スタート</translation>
    </message>
    <message>
        <location filename="../templates.py" line="47"/>
        <source>Analysis</source>
        <translation>解析</translation>
    </message>
    <message>
        <location filename="../templates.py" line="45"/>
        <source>Identify</source>
        <translation>同定</translation>
    </message>
    <message>
        <location filename="../templates.py" line="46"/>
        <source>Continuum</source>
        <translation>連続光</translation>
    </message>
</context>
<context>
    <name>Tutorial</name>
    <message>
        <location filename="../tutorial_guide.py" line="310"/>
        <source>Next</source>
        <translation>次へ</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="321"/>
        <source>Back</source>
        <translation>戻る</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="329"/>
        <source>Exit Tour</source>
        <translation>ツアーを終了</translation>
    </message>
    <message>
        <location filename="../tutorial_guide.py" line="337"/>
        <source>What is this?</source>
        <translation>これは何？</translation>
    </message>
</context>
</TS>
