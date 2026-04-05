"""Stage 4: LEARN — Record success/failure patterns to file-based memory.

Writes patterns, gotchas, and session metrics to memory/data/*.json.
Zero LLM calls — pure Python.
"""

from __future__ import annotations

import logging
from pathlib import Path

from memory.store import MemoryStore
from pipeline.v2.models import PipelineState

logger = logging.getLogger(__name__)


class LearnPhase:
    """Record session results for future learning."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parents[3] / "memory" / "data"
        self._store = MemoryStore(Path(data_dir))

    def learn(self, state: PipelineState) -> None:
        result = state.verify_fix_result
        if result is None:
            logger.info("Learn: no verify_fix_result to learn from")
            return

        # Save successful pattern
        if result.passed:
            pattern_key = f"{state.classification.task_type}_{state.strategy.approach}"
            self._store.save_pattern(
                key=pattern_key,
                file_features=state.file_context.get_feature_keys(),
                task_type=state.classification.task_type,
                winning_strategy={
                    "approach": state.strategy.approach,
                    "key_functions": list(state.strategy.key_functions),
                    "preprocessing": list(state.strategy.preprocessing_steps),
                },
                quality_score=result.best_score,
            )

        # Save gotchas from failed attempts (success or fail)
        for attempt in result.attempts:
            if attempt.error_category and attempt.error_message:
                gotcha_key = _derive_gotcha_key(attempt.error_category, attempt.error_message)
                self._store.save_gotcha(
                    key=gotcha_key,
                    detection=attempt.error_message[:200],
                    fix=_derive_fix_hint(attempt.error_category, attempt.error_message),
                )

        # Save session metrics
        self._store.save_session(
            task_type=state.classification.task_type,
            complexity=state.classification.complexity,
            strategy=state.strategy.approach,
            attempts=len(result.attempts),
            replan_count=state.replan_count,
            final_score=result.best_score,
            passed=result.passed,
        )

        logger.info(
            "Learn: session recorded",
            extra={
                "task_type": state.classification.task_type,
                "passed": result.passed,
                "final_score": result.best_score,
            },
        )


# ---------------------------------------------------------------------------
# Gotcha derivation helpers
# ---------------------------------------------------------------------------

_FIX_HINTS: dict[str, str] = {
    # Shell / pip
    "pip_install_in_code": (
        "pip install 文をコードに含めないこと。"
        "pandas, openpyxl, numpy はプリインストール済み。"
    ),

    # Excel-specific
    "merged_cells": (
        "openpyxl の ws.unmerge_cells() でマージを解除してから値を読み取ること。"
        "pandas の場合は pd.read_excel() が自動で処理するが、header 行にマージがあると列名が NaN になる。"
    ),
    "corrupt_excel": (
        "ファイルが破損または旧形式の可能性。"
        "openpyxl は .xlsx のみ対応。.xls の場合は xlrd を使うか、事前に xlsx に変換すること。"
    ),
    "legacy_xls": (
        ".xls (旧形式) は openpyxl 非対応。"
        "pd.read_excel(engine='xlrd') を使うか、ファイルを .xlsx に変換すること。"
    ),

    # CSV / text
    "encoding_error": (
        "ファイルのエンコーディングが UTF-8 でない可能性。"
        "pd.read_csv(encoding='cp932') や encoding='shift_jis' を試すこと。"
        "open() の場合は errors='replace' や chardet でエンコーディング検出。"
    ),
    "csv_parse_error": (
        "CSV のカラム数が行ごとに異なる可能性。"
        "pd.read_csv(on_bad_lines='skip') で不正行をスキップするか、"
        "sep パラメータでデリミタを明示すること (tab区切り: sep='\\t')。"
    ),

    # Data type / format
    "datetime_format": (
        "日付フォーマットが不統一の可能性。"
        "pd.to_datetime(col, format='mixed', dayfirst=False) を使うか、"
        "errors='coerce' で変換できない値を NaT にすること。"
    ),
    "nan_handling": (
        "NaN/欠損値が未処理。"
        "集計前に df.dropna(subset=[...]) または df.fillna(0) で処理すること。"
        "merge 時は key 列の NaN を事前に除去すること。"
    ),
    "value_cast_error": (
        "型変換の失敗。数値列に文字列が混入している可能性。"
        "pd.to_numeric(col, errors='coerce') で変換できない値を NaN にすること。"
    ),

    # Standard Python errors
    "import_error": (
        "必要なライブラリがインストールされていない。"
        "pandas, openpyxl, numpy はプリインストール済み。それ以外は使わないこと。"
    ),
    "syntax_error": (
        "構文エラー。シェルコマンドやコメント外の日本語がコードに混入していないか確認。"
        "f-string の中括弧の対応も要確認。"
    ),
    "type_error": (
        "型の不一致。merge キーの型を str に統一する、"
        "数値列の NaN を fillna() で処理するなど。"
    ),
    "key_error": (
        "カラム名の不一致。ファイル構造分析の headers を正確に参照すること。"
        "スペースや全角/半角の違いに注意。df.columns.str.strip() で前後空白を除去。"
    ),
    "index_error": (
        "インデックス範囲外。行数・列数をチェックしてからアクセスすること。"
        "空のシートやヘッダーのみのファイルを考慮すること。"
    ),
    "attribute_error": (
        "存在しないメソッドや属性にアクセスしている。"
        "ライブラリのバージョン違いか、オブジェクトの型が想定と異なる可能性。"
    ),
    "permission_error": (
        "ファイルの書き込み権限がない。OUTPUT_DIR 配下に出力すること。"
        "入力ファイルを上書きしないこと。"
    ),
    "file_not_found": (
        "入力ファイルパスは環境変数 INPUT_FILE から取得すること。"
        "出力は OUTPUT_DIR に保存すること。相対パスではなく環境変数を使う。"
    ),
    "memory_error": (
        "データが大きすぎてメモリ不足。"
        "pd.read_csv(chunksize=10000) でチャンク処理するか、"
        "必要な列だけ usecols で指定して読み込むこと。"
    ),
    "timeout": (
        "処理が重すぎてタイムアウト。"
        "チャンク処理、必要列のみ読み込み、不要なループの排除で高速化すること。"
    ),
    "runtime_error": (
        "実行時エラー。エラーメッセージを確認して原因を特定すること。"
    ),
}


def _derive_gotcha_key(error_category: str, error_message: str) -> str:
    """Derive a meaningful gotcha key from error details.

    Checks specific patterns in the error message first, then falls back
    to the error_category from _classify_error().
    """
    lower = error_message.lower()

    # Shell / pip
    if "pip install" in lower or "pip" in lower and "module" not in lower:
        return "pip_install_in_code"

    # Excel-specific
    if "mergedcell" in lower or "merged cell" in lower:
        return "merged_cells"
    if "not a zip file" in lower or "invalidfileexception" in lower:
        return "corrupt_excel"

    # Encoding
    if "unicodedecodeerror" in lower or "codec" in lower:
        return "encoding_error"

    # Data issues
    if "nan" in lower and ("convert" in lower or "fillna" in lower or "float" in lower):
        return "nan_handling"
    if "to_datetime" in lower or "strftime" in lower:
        return "datetime_format"

    return error_category


def _derive_fix_hint(error_category: str, error_message: str) -> str:
    """Generate an actionable fix hint based on error category.

    Uses the same key derivation as gotcha storage, then looks up the
    hardcoded hint from _FIX_HINTS.
    """
    key = _derive_gotcha_key(error_category, error_message)
    return _FIX_HINTS.get(key, _FIX_HINTS.get(error_category, f"エラーカテゴリ '{error_category}' を回避するアプローチを使うこと。"))


# ---------------------------------------------------------------------------
# Session insight extraction (cross-session learning)
# ---------------------------------------------------------------------------


def _extract_insights(
    *,
    attempts: list,
    task_type: str,
    strategy: str,
    passed: bool,
    replan_count: int,
) -> list[dict]:
    """Extract structured insights from attempt history.

    Identifies recurring error patterns and strategy failures.
    Pure Python — no LLM calls.
    """
    from collections import Counter

    insights: list[dict] = []

    # Count error categories
    error_counts: Counter = Counter()
    for a in attempts:
        if a.error_category:
            error_counts[a.error_category] += 1

    # Repeated errors → insight
    for category, count in error_counts.items():
        if count >= 2:
            fix_hint = _FIX_HINTS.get(category, "")
            insights.append({
                "pattern": category,
                "trigger": f"{category} が {count} 回発生",
                "prevention": fix_hint or f"エラーカテゴリ '{category}' を回避すること",
                "source_task_type": task_type,
            })

    # Replan occurred → initial strategy was wrong
    if replan_count > 0 and not passed:
        insights.append({
            "pattern": f"strategy_failure_{strategy}",
            "trigger": f"戦略 '{strategy}' で {replan_count} 回 replan が発生",
            "prevention": f"タスクタイプ '{task_type}' では '{strategy}' 以外の戦略を検討すること",
            "source_task_type": task_type,
        })

    return insights
