"""LLM-as-Judge: automatic code quality evaluation.

Uses a separate LLM call to evaluate generated code on multiple dimensions.
Results are registered as Langfuse scores when tracing is enabled.
"""

from __future__ import annotations

import json
import logging

from core.config import Settings
from services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """\
あなたはPythonコードの品質評価エキスパートです。

以下のタスクに対して生成されたPythonコードを評価してください。

【タスク】
{task}

【生成されたコード】
{code}

以下の4つの観点で0〜10のスコアを付けてください:
- correctness: タスクの要件を正しく満たしているか
- readability: コードが読みやすく、コメントが適切か
- efficiency: 無駄のない効率的な実装か
- robustness: エッジケースやエラー処理が考慮されているか

JSON形式で返答してください:
{{
  "correctness": 8,
  "readability": 7,
  "efficiency": 6,
  "robustness": 5,
  "overall": 6.5,
  "comment": "総合的な評価コメント"
}}
"""


def evaluate_code(
    task: str,
    code: str,
    settings: Settings,
) -> dict | None:
    """Evaluate generated code quality using LLM-as-Judge.

    Returns dict with scores or None if evaluation fails.
    """
    if not code or not task:
        return None

    try:
        client = OpenAIClient(settings)
        prompt = JUDGE_PROMPT.replace("{task}", task).replace("{code}", code)

        raw = client.generate_code(
            system_prompt="あなたはコード品質評価の専門家です。JSONのみ返してください。",
            user_prompt=prompt,
        )

        scores = json.loads(raw)

        required = ["correctness", "readability", "efficiency", "robustness", "overall"]
        for field in required:
            if field not in scores:
                return None
            scores[field] = float(scores[field])

        logger.info(
            "LLM judge evaluation completed",
            extra={
                "overall": scores["overall"],
                "correctness": scores["correctness"],
            },
        )
        return scores

    except Exception:
        logger.warning("LLM judge evaluation failed", exc_info=True)
        return None


def evaluate_and_score(
    task: str,
    code: str,
    settings: Settings,
    trace=None,
) -> dict | None:
    """Evaluate code and register scores in Langfuse trace."""
    scores = evaluate_code(task, code, settings)
    if scores is None:
        return None

    if trace is not None:
        for dimension in ["correctness", "readability", "efficiency", "robustness", "overall"]:
            value = scores.get(dimension)
            if value is not None:
                trace.score(
                    f"judge_{dimension}",
                    float(value),
                    data_type="NUMERIC",
                    comment=scores.get("comment", ""),
                )

    return scores
