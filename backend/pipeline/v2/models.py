"""Adaptive Pipeline v2 data models.

All models are frozen (immutable) except PipelineState which is mutated
across stages (analogous to Auto-Claude's implementation_plan.json).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ---------------------------------------------------------------------------
# Stage 1: UNDERSTAND
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComplexitySignals:
    """Structural complexity indicators derived from Excel analysis."""

    multi_sheet_refs: bool = False
    cross_sheet_formulas: list[str] = field(default_factory=list)
    nested_headers: bool = False
    mixed_dtypes_per_column: list[str] = field(default_factory=list)
    estimated_total_cells: int = 0


@dataclass(frozen=True)
class FileContext:
    """LLM-free Excel structure analysis result.

    Reuses SheetInfo from excel/xlsx_parser.py for sheet-level data and
    adds file-wide signals needed by the v2 pipeline.
    """

    sheets: list[dict] = field(default_factory=list)  # xlsx_parser.SheetInfo as dicts
    has_merged_cells: bool = False
    has_formulas: bool = False
    has_charts: bool = False
    has_pivot_tables: bool = False
    file_size_mb: float = 0.0
    complexity_signals: ComplexitySignals = field(default_factory=ComplexitySignals)

    def to_prompt(self) -> str:
        """Format for LLM prompt injection."""
        lines: list[str] = []
        for s in self.sheets:
            name = s.get("name", "Sheet")
            headers = s.get("headers", [])
            types = s.get("types", {})
            row_count = s.get("total_rows", 0)
            merged = s.get("merged_cells", ())
            lines.append(f"## {name} ({row_count} rows)")
            lines.append(f"Headers: {headers}")
            lines.append(f"Types: {types}")
            if merged:
                lines.append(f"Merged cells: {list(merged)}")

        flags: list[str] = []
        if self.has_merged_cells:
            flags.append("merged_cells")
        if self.has_formulas:
            flags.append("formulas")
        if self.has_charts:
            flags.append("charts")
        if self.has_pivot_tables:
            flags.append("pivot_tables")
        if flags:
            lines.append(f"File features: {flags}")

        cs = self.complexity_signals
        if cs.multi_sheet_refs:
            lines.append("Complexity: multi-sheet references detected")
        if cs.nested_headers:
            lines.append("Complexity: nested/multi-row headers detected")
        if cs.mixed_dtypes_per_column:
            lines.append(f"Complexity: mixed dtypes in columns {cs.mixed_dtypes_per_column}")

        return "\n".join(lines)

    def get_feature_keys(self) -> list[str]:
        """Return feature keys for memory search."""
        keys: list[str] = []
        if self.has_merged_cells:
            keys.append("merged_cells")
        if self.has_formulas:
            keys.append("formulas")
        if self.complexity_signals.multi_sheet_refs:
            keys.append("multi_sheet")
        if self.complexity_signals.nested_headers:
            keys.append("nested_headers")
        if len(self.sheets) > 1:
            keys.append("multi_sheet")
        return list(set(keys))


@dataclass(frozen=True)
class TaskClassification:
    """Task complexity classification."""

    complexity: Literal["simple", "standard", "complex"] = "standard"
    task_type: str = "general"  # aggregation, merge, pivot, formatting, etc.
    estimated_difficulty: float = 0.5


@dataclass(frozen=True)
class StrategyStep:
    """A single step in a COMPLEX task's staged generation plan."""

    id: int = 0
    action: str = ""
    verify: str = ""
    expected_files: list[str] | None = None
    expected_in_output: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Strategy:
    """Code generation strategy decided in UNDERSTAND stage."""

    approach: str = "pandas"  # pandas, openpyxl, xlsxwriter, hybrid
    key_functions: list[str] = field(default_factory=list)
    preprocessing_steps: list[str] = field(default_factory=list)
    output_format: str = "xlsx"
    risk_factors: list[str] = field(default_factory=list)
    steps: list[StrategyStep] | None = None  # Only for COMPLEX

    def to_prompt(self) -> str:
        """Format for LLM prompt injection."""
        lines = [
            f"Library: {self.approach}",
            f"Key functions: {self.key_functions}",
            f"Preprocessing: {self.preprocessing_steps}",
            f"Output format: {self.output_format}",
        ]
        if self.risk_factors:
            lines.append(f"Risk factors: {self.risk_factors}")
        if self.steps:
            lines.append("Steps:")
            for s in self.steps:
                lines.append(f"  {s.id}. {s.action} (verify: {s.verify})")
        return "\n".join(lines)


@dataclass(frozen=True)
class MemoryContext:
    """Past learnings retrieved from memory."""

    patterns: list[dict] = field(default_factory=list)
    gotchas: list[dict] = field(default_factory=list)

    def to_prompt(self) -> str:
        if not self.patterns and not self.gotchas:
            return ""
        lines: list[str] = []
        if self.patterns:
            lines.append("## Past Successful Patterns")
            for p in self.patterns[:5]:
                lines.append(f"- {p.get('task_type', '?')}: {p.get('winning_strategy', {}).get('approach', '?')}")
        if self.gotchas:
            lines.append("## Known Gotchas")
            for g in self.gotchas[:5]:
                lines.append(f"- {g.get('detection', '?')} → {g.get('fix', '?')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 2: GENERATE
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerateResult:
    """Output of the GENERATE stage."""

    code: str = ""
    summary: str = ""
    steps: list[str] = field(default_factory=list)
    tips: str = ""
    success: bool = True
    replan_needed: bool = False


@dataclass(frozen=True)
class StepVerification:
    """Result of verifying a single COMPLEX step."""

    passed: bool = True
    error: str = ""
    error_type: str = ""  # execution, no_output, suspicious_output, missing_file


# ---------------------------------------------------------------------------
# Stage 3: VERIFY-FIX
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """A single problem detected by the Verifier."""

    level: str = "execution"  # execution, quality, semantic
    description: str = ""
    severity: str = "major"  # critical, major, minor


@dataclass(frozen=True)
class VerificationResult:
    """Output of the unified Verifier."""

    passed: bool = False
    execution_error: str | None = None
    quality_score: float = 0.0
    semantic_score: float = 0.0
    combined_score: float = 0.0
    issues: list[Issue] = field(default_factory=list)
    fix_guidance: str = ""


@dataclass(frozen=True)
class Attempt:
    """Record of one verify-fix iteration."""

    code: str = ""
    code_hash: str = ""
    approach: str = ""
    error_category: str | None = None
    error_message: str | None = None
    quality_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class FixRequest:
    """Structured repair instructions passed to the Fixer.

    Analogous to Auto-Claude's QA_FIX_REQUEST.md.
    """

    issues: list[Issue] = field(default_factory=list)
    must_not_repeat: list[str] = field(default_factory=list)
    previous_approaches: list[str] = field(default_factory=list)
    fix_guidance: str = ""


@dataclass(frozen=True)
class RecoveryDecision:
    """Output of RecoveryManager.analyze()."""

    action: str = "fix"  # fix, replan, escalate
    fix_request: FixRequest | None = None
    replan_reason: str | None = None
    suggested_strategy_change: str | None = None


@dataclass(frozen=True)
class VerifyFixResult:
    """Final result of the VERIFY-FIX loop."""

    best_code: str = ""
    best_score: float = 0.0
    attempts: list[Attempt] = field(default_factory=list)
    passed: bool = False
    replan_needed: bool = False


# ---------------------------------------------------------------------------
# Pipeline State (mutable — stages write to this)
# ---------------------------------------------------------------------------


@dataclass
class PipelineState:
    """Mutable state shared across all v2 stages.

    Analogous to Auto-Claude's implementation_plan.json.
    Unlike other models in this module, this is NOT frozen because stages
    progressively populate it.
    """

    task: str = ""
    file_id: str | None = None
    file_context: FileContext = field(default_factory=FileContext)
    classification: TaskClassification = field(default_factory=TaskClassification)
    strategy: Strategy = field(default_factory=Strategy)
    memory_context: MemoryContext = field(default_factory=MemoryContext)
    generation_result: GenerateResult | None = None
    verify_fix_result: VerifyFixResult | None = None
    attempt_history: list[Attempt] = field(default_factory=list)
    replan_count: int = 0
    max_replan: int = 2
    # Runtime references (not serialized)
    expected_file_path: str | None = None
    rubric: dict | None = None
