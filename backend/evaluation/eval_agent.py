"""Evaluation agent: LLM-based semantic comparison of Excel outputs.

Compares expected vs actual Excel output using an LLM to assess
semantic correctness, data integrity, and completeness.
Unlike the mechanical excel_comparator, this agent understands
column reordering, label variations, and partial correctness.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from core.config import Settings
from infra.openai_client import OpenAIClient
from infra.prompt_loader import load_prompt
from excel.xlsx_parser import build_file_context, parse_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvalAgentResult:
    """Immutable result of the LLM evaluation agent."""

    semantic_correctness: float  # 0-10
    data_integrity: float        # 0-10
    completeness: float          # 0-10
    overall: float               # 0-10
    reasoning: str


def _file_to_context(path: str) -> str:
    """Parse an Excel/CSV file and return a text context string."""
    sheets = parse_file(path)
    context = build_file_context(sheets)
    return context or "(empty file)"


def evaluate_output(
    task: str,
    actual_path: str,
    expected_path: str,
    settings: Settings,
    structured_report: str | None = None,
) -> EvalAgentResult | None:
    """Evaluate actual output against expected output using LLM.

    Args:
        task: Original task description.
        actual_path: Path to the actual output file.
        expected_path: Path to the expected output file.
        settings: Application settings (for OpenAI client).
        structured_report: Optional summary text from structured_comparator
                           (value-based scan results, color checks, etc.).

    Returns:
        Frozen EvalAgentResult with scores, or None if evaluation fails.
    """
    try:
        expected_context = _file_to_context(expected_path)
        actual_context = _file_to_context(actual_path)
    except Exception:
        logger.warning("Failed to parse files for eval agent", exc_info=True)
        return None

    try:
        template = load_prompt("eval_agent", settings)
        if structured_report:
            actual_context = (
                actual_context
                + "\n\n【構造化比較レポート】\n"
                "OEE等の計算値はラベル検索で行位置によらず確認済みです。\n"
                + structured_report
            )
        prompt = (
            template
            .replace("{task}", task)
            .replace("{expected_context}", expected_context)
            .replace("{actual_context}", actual_context)
        )

        client = OpenAIClient(settings)
        raw = client.generate_code(
            system_prompt="あなたはExcel出力の正確性を評価する専門家です。JSONのみ返してください。",
            user_prompt=prompt,
        )

        scores = json.loads(raw)

        required_fields = ["semantic_correctness", "data_integrity", "completeness", "overall"]
        for field in required_fields:
            if field not in scores:
                logger.warning("Eval agent missing field: %s", field)
                return None
            scores[field] = float(scores[field])

        result = EvalAgentResult(
            semantic_correctness=scores["semantic_correctness"],
            data_integrity=scores["data_integrity"],
            completeness=scores["completeness"],
            overall=scores["overall"],
            reasoning=scores.get("reasoning", ""),
        )

        logger.info(
            "Eval agent completed",
            extra={
                "overall": result.overall,
                "semantic_correctness": result.semantic_correctness,
                "data_integrity": result.data_integrity,
                "completeness": result.completeness,
            },
        )
        return result

    except Exception:
        logger.warning("Eval agent evaluation failed", exc_info=True)
        return None
