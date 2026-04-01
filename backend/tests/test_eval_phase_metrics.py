"""Tests for per-phase token metrics in the eval harness.

TDD RED phase: these tests define the expected API before implementation.

Strategy:
- orchestrate() snapshots total_tokens before each phase, emits per-phase deltas
  in the final result_payload (Phase C complete).
- EvalMetrics gets a new phase_tokens: dict[str, int] field.
- EvalRunner extracts phase_tokens from the Phase C complete payload.
- EvalReport.summary_table() adds avg_phase_tokens per architecture.
"""

from __future__ import annotations

import json
from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest

from eval.models import ArchitectureConfig, EvalMetrics, EvalResult, TestCase
from eval.runner import EvalRunner
from eval.report import EvalReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_settings(overrides: dict | None = None) -> MagicMock:
    s = MagicMock()
    s.openai_api_key = "test-key"
    s.openai_model = "gpt-4o"
    s.upload_dir = "./uploads"
    s.output_dir = "./outputs"
    s.exec_timeout = 30
    s.reflection_enabled = True
    s.reflection_max_steps = 3
    s.debug_loop_enabled = True
    s.debug_retry_limit = 3
    s.skills_enabled = True
    if overrides:
        for k, v in overrides.items():
            setattr(s, k, v)
    return s


def _make_phase_c_payload(
    python_code: str = "print(1)",
    phase_tokens: dict[str, int] | None = None,
    total_tokens: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    api_calls: int = 0,
    debug_retries: int = 0,
) -> str:
    payload: dict = {
        "python_code": python_code,
        "summary": "test summary",
        "steps": [],
        "tips": "",
        "debug_retries": debug_retries,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "api_calls": api_calls,
    }
    if phase_tokens is not None:
        payload["phase_tokens"] = phase_tokens
    return json.dumps(payload, ensure_ascii=False)


def _make_entry(phase: str, action: str, content: str) -> MagicMock:
    entry = MagicMock()
    entry.phase = phase
    entry.action = action
    entry.content = content
    entry.timestamp = "2026-03-28T00:00:00+00:00"
    return entry


# ---------------------------------------------------------------------------
# EvalMetrics — phase_tokens field
# ---------------------------------------------------------------------------


class TestEvalMetricsPhaseTokens:
    """EvalMetrics should have a phase_tokens field."""

    def test_phase_tokens_defaults_to_empty_dict(self) -> None:
        m = EvalMetrics(success=True, total_duration_ms=100)
        assert hasattr(m, "phase_tokens")
        assert isinstance(m.phase_tokens, dict)
        assert m.phase_tokens == {}

    def test_phase_tokens_can_be_set(self) -> None:
        m = EvalMetrics(
            success=True,
            total_duration_ms=100,
            phase_tokens={"A": 500, "B": 300, "C": 1200, "D": 3000},
        )
        assert m.phase_tokens["A"] == 500
        assert m.phase_tokens["B"] == 300
        assert m.phase_tokens["C"] == 1200
        assert m.phase_tokens["D"] == 3000

    def test_phase_tokens_is_included_in_to_dict(self) -> None:
        """phase_tokens should appear in EvalResult.to_dict() metrics."""
        m = EvalMetrics(
            success=True,
            total_duration_ms=100,
            phase_tokens={"A": 400, "C": 800},
        )
        result = EvalResult(
            architecture_id="v1",
            test_case_id="c1",
            metrics=m,
            agent_log=[],
        )
        d = result.to_dict()
        assert "phase_tokens" in d["metrics"]
        assert d["metrics"]["phase_tokens"]["A"] == 400
        assert d["metrics"]["phase_tokens"]["C"] == 800

    def test_eval_metrics_frozen_with_phase_tokens(self) -> None:
        """EvalMetrics remains frozen (immutable) with the new field."""
        m = EvalMetrics(
            success=True,
            total_duration_ms=100,
            phase_tokens={"C": 1000},
        )
        with pytest.raises(AttributeError):
            m.phase_tokens = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# orchestrate() — phase_tokens in result_payload
# ---------------------------------------------------------------------------


class TestOrchestratePhaseTokens:
    """orchestrate() should include phase_tokens in the Phase C complete payload."""

    @pytest.mark.asyncio
    async def test_result_payload_includes_phase_tokens(self) -> None:
        """The Phase C complete payload must contain phase_tokens dict."""
        from services.agent_orchestrator import orchestrate

        mock_settings = MagicMock()
        mock_settings.reflection_enabled = False
        mock_settings.debug_loop_enabled = False
        mock_settings.skills_enabled = False
        mock_settings.upload_dir = "./uploads"
        mock_settings.output_dir = "./outputs"
        mock_settings.exec_timeout = 30
        mock_settings.debug_retry_limit = 3
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"

        mock_response = json.dumps({
            "summary": "test",
            "python_code": "print(1)",
            "steps": [],
            "tips": "",
        })

        with patch("services.agent_orchestrator.OpenAIClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.generate_code.return_value = mock_response
            # Use real ints so isinstance checks pass
            mock_client.total_tokens = 0
            mock_client.prompt_tokens = 0
            mock_client.completion_tokens = 0
            mock_client.api_calls = 0
            mock_client_cls.return_value = mock_client

            entries = []
            async for entry in orchestrate("task", None, mock_settings):
                entries.append(entry)

        result_entry = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(result_entry.content)
        assert "phase_tokens" in payload
        assert isinstance(payload["phase_tokens"], dict)

    @pytest.mark.asyncio
    async def test_phase_c_token_delta_is_tracked(self) -> None:
        """When only Phase C runs, phase_tokens['C'] should equal total tokens used."""
        from services.agent_orchestrator import orchestrate

        mock_settings = MagicMock()
        mock_settings.reflection_enabled = False
        mock_settings.debug_loop_enabled = False
        mock_settings.skills_enabled = False
        mock_settings.upload_dir = "./uploads"
        mock_settings.output_dir = "./outputs"
        mock_settings.exec_timeout = 30
        mock_settings.debug_retry_limit = 3
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"

        mock_response = json.dumps({
            "summary": "test",
            "python_code": "print(1)",
            "steps": [],
            "tips": "",
        })

        # Simulate: before Phase C, total_tokens=0; after Phase C, total_tokens=1500
        call_count = 0

        class FakeClient:
            total_tokens = 0
            prompt_tokens = 0
            completion_tokens = 0
            api_calls = 0

            def generate_code(self, system_prompt, user_prompt):
                nonlocal call_count
                call_count += 1
                # After the call, increment counters (simulating a real API call)
                self.__class__.total_tokens += 1500
                self.__class__.prompt_tokens += 1000
                self.__class__.completion_tokens += 500
                self.__class__.api_calls += 1
                return mock_response

        with patch("services.agent_orchestrator.OpenAIClient", return_value=FakeClient()):
            entries = []
            async for entry in orchestrate("task", None, mock_settings):
                entries.append(entry)

        result_entry = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(result_entry.content)
        assert "phase_tokens" in payload
        # Phase C should have captured the 1500 tokens used
        assert payload["phase_tokens"].get("C", 0) == 1500

    @pytest.mark.asyncio
    async def test_all_phases_tracked_when_reflection_enabled(self) -> None:
        """When A, B, C all run, phase_tokens should include keys for each."""
        from services.agent_orchestrator import orchestrate

        mock_settings = MagicMock()
        mock_settings.reflection_enabled = True
        mock_settings.debug_loop_enabled = False
        mock_settings.skills_enabled = False
        mock_settings.upload_dir = "./uploads"
        mock_settings.output_dir = "./outputs"
        mock_settings.exec_timeout = 30
        mock_settings.debug_retry_limit = 3
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"

        # Phase A result
        phase_a_result = MagicMock()
        phase_a_result.success = True
        phase_a_result.exploration_output = "explored"

        # Phase B result
        phase_b_result = MagicMock()
        phase_b_result.needs_custom_tool = False
        phase_b_result.reason = "ok"
        phase_b_result.tool_output = ""

        # Phase C response
        phase_c_response = json.dumps({
            "summary": "test",
            "python_code": "print(1)",
            "steps": [],
            "tips": "",
        })

        token_sequence = [300, 500, 1200]  # tokens per phase call
        call_index = [0]

        class CountingClient:
            total_tokens = 0
            prompt_tokens = 0
            completion_tokens = 0
            api_calls = 0

            def generate_code(self, system_prompt, user_prompt):
                idx = call_index[0]
                delta = token_sequence[idx] if idx < len(token_sequence) else 100
                call_index[0] += 1
                self.__class__.total_tokens += delta
                self.__class__.prompt_tokens += delta * 2 // 3
                self.__class__.completion_tokens += delta // 3
                self.__class__.api_calls += 1
                return phase_c_response

        file_id = "test-file-id"

        with (
            patch("services.agent_orchestrator.OpenAIClient", return_value=CountingClient()),
            patch("services.agent_orchestrator._resolve_file_context", return_value="file context"),
            patch("services.phase_handlers.run_phase_a", return_value=phase_a_result) as mock_a,
            patch("services.phase_handlers.run_phase_b", return_value=phase_b_result) as mock_b,
            patch("services.agent_orchestrator.run_phase_c") as mock_c,
        ):
            # run_phase_a and run_phase_b are async — make them awaitable
            import asyncio
            mock_a.return_value = phase_a_result
            mock_a.side_effect = None

            async def fake_phase_a(**kwargs):
                CountingClient.total_tokens += 300
                CountingClient.prompt_tokens += 200
                CountingClient.completion_tokens += 100
                CountingClient.api_calls += 1
                return phase_a_result

            async def fake_phase_b(**kwargs):
                CountingClient.total_tokens += 500
                CountingClient.prompt_tokens += 333
                CountingClient.completion_tokens += 167
                CountingClient.api_calls += 1
                return phase_b_result

            async def fake_phase_c(**kwargs):
                CountingClient.total_tokens += 1200
                CountingClient.prompt_tokens += 800
                CountingClient.completion_tokens += 400
                CountingClient.api_calls += 1
                phase_c_mock = MagicMock()
                phase_c_mock.python_code = "print(1)"
                phase_c_mock.summary = "test"
                phase_c_mock.steps = []
                phase_c_mock.tips = ""
                return phase_c_mock

            mock_a.side_effect = fake_phase_a
            mock_b.side_effect = fake_phase_b
            mock_c.side_effect = fake_phase_c

            entries = []
            async for entry in orchestrate("task", file_id, mock_settings):
                entries.append(entry)

        result_entry = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(result_entry.content)
        assert "phase_tokens" in payload
        phase_tokens = payload["phase_tokens"]

        # All three phases should have token counts
        assert "A" in phase_tokens
        assert "B" in phase_tokens
        assert "C" in phase_tokens
        # Each phase delta should be positive
        assert phase_tokens["A"] == 300
        assert phase_tokens["B"] == 500
        assert phase_tokens["C"] == 1200


# ---------------------------------------------------------------------------
# EvalRunner — extracts phase_tokens from Phase C payload
# ---------------------------------------------------------------------------


class TestEvalRunnerPhaseTokenExtraction:
    """EvalRunner.run_single should populate metrics.phase_tokens."""

    @pytest.mark.asyncio
    async def test_phase_tokens_captured_from_payload(self) -> None:
        """phase_tokens in Phase C complete payload flows into metrics."""
        arch = ArchitectureConfig(id="v1", phases=["A", "B", "C"])
        case = TestCase(id="c1", task="t", description="d")

        phase_tokens_in_payload = {"A": 300, "B": 500, "C": 1200}

        entry = _make_entry(
            "C",
            "complete",
            _make_phase_c_payload(
                total_tokens=2000,
                phase_tokens=phase_tokens_in_payload,
            ),
        )

        async def mock_orchestrate(*args, **kwargs):
            yield entry

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        assert result.metrics.phase_tokens == phase_tokens_in_payload
        assert result.metrics.phase_tokens["A"] == 300
        assert result.metrics.phase_tokens["B"] == 500
        assert result.metrics.phase_tokens["C"] == 1200

    @pytest.mark.asyncio
    async def test_phase_tokens_defaults_to_empty_when_missing(self) -> None:
        """If phase_tokens not in payload (old format), metrics.phase_tokens is {}."""
        arch = ArchitectureConfig(id="v1", phases=["C"])
        case = TestCase(id="c1", task="t", description="d")

        # Payload without phase_tokens key (legacy format)
        entry = _make_entry(
            "C",
            "complete",
            _make_phase_c_payload(total_tokens=1000),  # no phase_tokens arg
        )

        async def mock_orchestrate(*args, **kwargs):
            yield entry

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        assert result.metrics.phase_tokens == {}

    @pytest.mark.asyncio
    async def test_phase_tokens_with_debug_phase(self) -> None:
        """phase_tokens can include D for debug loop tokens."""
        arch = ArchitectureConfig(id="v1", phases=["C", "D"])
        case = TestCase(id="c1", task="t", description="d")

        phase_tokens_in_payload = {"C": 1200, "D": 800}

        entry = _make_entry(
            "C",
            "complete",
            _make_phase_c_payload(
                total_tokens=2000,
                phase_tokens=phase_tokens_in_payload,
            ),
        )

        async def mock_orchestrate(*args, **kwargs):
            yield entry

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        assert result.metrics.phase_tokens["C"] == 1200
        assert result.metrics.phase_tokens["D"] == 800

    @pytest.mark.asyncio
    async def test_phase_tokens_does_not_break_existing_token_extraction(self) -> None:
        """Adding phase_tokens does not break extraction of total/prompt/completion tokens."""
        arch = ArchitectureConfig(id="v1", phases=["C"])
        case = TestCase(id="c1", task="t", description="d")

        entry = _make_entry(
            "C",
            "complete",
            _make_phase_c_payload(
                total_tokens=2500,
                prompt_tokens=1700,
                completion_tokens=800,
                api_calls=4,
                phase_tokens={"C": 2500},
            ),
        )

        async def mock_orchestrate(*args, **kwargs):
            yield entry

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        # Existing fields still work
        assert result.metrics.total_tokens == 2500
        assert result.metrics.prompt_tokens == 1700
        assert result.metrics.completion_tokens == 800
        assert result.metrics.api_calls == 4
        # New field also populated
        assert result.metrics.phase_tokens == {"C": 2500}


# ---------------------------------------------------------------------------
# EvalReport — avg_phase_tokens in summary_table
# ---------------------------------------------------------------------------


class TestEvalReportPhaseTokenSummary:
    """EvalReport.summary_table() should include avg_phase_tokens per architecture."""

    def _make_result(
        self,
        arch_id: str,
        case_id: str,
        phase_tokens: dict[str, int],
        model: str = "gpt-4o",
    ) -> EvalResult:
        return EvalResult(
            architecture_id=arch_id,
            test_case_id=case_id,
            model=model,
            metrics=EvalMetrics(
                success=True,
                total_duration_ms=1000,
                total_tokens=sum(phase_tokens.values()),
                phase_tokens=phase_tokens,
            ),
            agent_log=[],
            generated_code="print(1)",
        )

    def test_summary_table_includes_avg_phase_tokens(self) -> None:
        """summary_table should include avg_phase_tokens key."""
        results = [
            self._make_result("v1", "c1", {"A": 300, "B": 500, "C": 1200}),
            self._make_result("v1", "c2", {"A": 400, "B": 600, "C": 1400}),
        ]
        report = EvalReport(results)
        table = report.summary_table()
        assert "avg_phase_tokens" in table["v1"]

    def test_avg_phase_tokens_computed_correctly(self) -> None:
        """avg_phase_tokens should be the mean per phase across runs."""
        results = [
            self._make_result("v1", "c1", {"A": 300, "B": 500, "C": 1200}),
            self._make_result("v1", "c2", {"A": 500, "B": 700, "C": 1600}),
        ]
        report = EvalReport(results)
        table = report.summary_table()
        avg = table["v1"]["avg_phase_tokens"]

        # avg A = (300 + 500) / 2 = 400
        assert abs(avg["A"] - 400.0) < 0.01
        # avg B = (500 + 700) / 2 = 600
        assert abs(avg["B"] - 600.0) < 0.01
        # avg C = (1200 + 1600) / 2 = 1400
        assert abs(avg["C"] - 1400.0) < 0.01

    def test_avg_phase_tokens_handles_missing_phases(self) -> None:
        """If some runs don't have a phase (e.g., no Phase A), averages should still work."""
        results = [
            self._make_result("v1", "c1", {"C": 1200}),  # no A or B
            self._make_result("v1", "c2", {"A": 400, "C": 1400}),  # has A
        ]
        report = EvalReport(results)
        table = report.summary_table()
        avg = table["v1"]["avg_phase_tokens"]

        # C appears in both: avg = (1200 + 1400) / 2 = 1300
        assert abs(avg["C"] - 1300.0) < 0.01
        # A appears in 1 of 2 runs: avg over runs that have it = 400 / 1 = 400
        # OR avg over all runs = 400 / 2 = 200
        # Either interpretation is acceptable; test that key exists and is a float
        assert "A" in avg
        assert isinstance(avg["A"], float)

    def test_avg_phase_tokens_empty_results(self) -> None:
        """summary_table with no results should not crash."""
        report = EvalReport([])
        table = report.summary_table()
        assert table == {}

    def test_avg_phase_tokens_no_phase_tokens_field(self) -> None:
        """Results with empty phase_tokens should produce empty avg_phase_tokens."""
        results = [
            EvalResult(
                architecture_id="v2",
                test_case_id="c1",
                model="gpt-4o",
                metrics=EvalMetrics(
                    success=True,
                    total_duration_ms=1000,
                    total_tokens=1000,
                    phase_tokens={},  # empty
                ),
                agent_log=[],
                generated_code="print(1)",
            ),
        ]
        report = EvalReport(results)
        table = report.summary_table()
        assert "avg_phase_tokens" in table["v2"]
        assert table["v2"]["avg_phase_tokens"] == {}

    def test_avg_phase_tokens_multiple_architectures(self) -> None:
        """Each architecture should have independent avg_phase_tokens."""
        results = [
            self._make_result("v1", "c1", {"A": 300, "C": 1200}),
            self._make_result("v2", "c1", {"C": 2000}),
        ]
        report = EvalReport(results)
        table = report.summary_table()

        # v1 has A and C
        assert "A" in table["v1"]["avg_phase_tokens"]
        assert "C" in table["v1"]["avg_phase_tokens"]

        # v2 only has C
        assert "C" in table["v2"]["avg_phase_tokens"]
        # A is optional in v2 — if present it's 0, if absent that's fine too
        # Just verify C is correct
        assert abs(table["v2"]["avg_phase_tokens"]["C"] - 2000.0) < 0.01

    def test_to_dict_includes_phase_token_summary(self) -> None:
        """EvalReport.to_dict() should include avg_phase_tokens in summary."""
        results = [
            self._make_result("v1", "c1", {"C": 1000}),
        ]
        report = EvalReport(results)
        d = report.to_dict()
        assert "avg_phase_tokens" in d["summary"]["v1"]
