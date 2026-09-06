from chappy_user_manual_generator.models import (
    OperationFlow,
    OperationSection,
    OperationSectionBlock,
    OperationSectionItem,
    OperationStep,
    RelatedLink,
)
from chappy_user_manual_generator.pipeline import _write_operation_flow
from chappy.i18n import get_language_switcher


def test_write_operation_flow_generates_sections(tmp_path):
    lm = get_language_switcher()
    previous = lm.current_language
    try:
        lm.set_language("ja")
    except Exception:
        # If language switching fails, ensure we still attempt with default.
        previous = lm.current_language

    flow = OperationFlow(
        slug="sample-flow",
        title="サンプルフロー",
        summary="概要の説明です。",
        steps=(OperationStep(order=1, action="操作", expected="結果"),),
        prerequisites=("前提A",),
        notes=("注意A",),
        related_links=(
            RelatedLink(
                label="共通の画面要素", path="../screens/main_window/common/MainWindow.md"
            ),
        ),
    )

    try:
        _write_operation_flow(flow, base_dir=tmp_path, version="snapshot")

        content = (tmp_path / "sample-flow.md").read_text(encoding="utf-8")
        lines = content.splitlines()

        assert lines[0] == "# サンプルフロー"
        assert lines[1] == ""
        assert lines[2] == "概要の説明です。"
        assert "## このワークフローについて" not in content
        assert "| 1 | 操作 | 結果 |" in content
        assert "- 前提A" in content
        assert "- 注意A" in content or "- 注意A\n" in content
        assert "- [共通の画面要素](../screens/main_window/common/MainWindow.md)" in content
    finally:
        lm.set_language(previous)


def test_write_operation_flow_supports_section_only_flow(tmp_path):
    lm = get_language_switcher()
    previous = lm.current_language
    try:
        lm.set_language("ja")
    except Exception:
        previous = lm.current_language

    flow = OperationFlow(
        slug="catalog-flow",
        title="カタログ型フロー",
        summary="操作をカテゴリ別に整理した構成です。",
        steps=(),
        sections=(
            OperationSection(
                heading="目的別の操作ガイド",
                description="需要に応じて参照してください。",
                items=(
                    OperationSectionItem(
                        title="状態を確認する",
                        description="サイドパネルでグループとラインを選択し、メタデータを確認します。",
                    ),
                ),
                blocks=(
                    OperationSectionBlock(
                        content="| 操作 | 手順 |\n| --- | --- |\n| 確認 | 選択 |\n"
                    ),
                ),
            ),
        ),
        notes=(),
        prerequisites=("グループを含むプロジェクトがロードされていること。",),
    )

    try:
        _write_operation_flow(flow, base_dir=tmp_path, version="snapshot")

        content = (tmp_path / "catalog-flow.md").read_text(encoding="utf-8")
        assert "## 目的別の操作ガイド" in content
        assert "| 操作 | 手順 |" in content
        assert "## 操作手順" not in content
    finally:
        lm.set_language(previous)
