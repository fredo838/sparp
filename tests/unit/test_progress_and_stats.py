import pytest
import datetime
from typing import Any, Dict, List, Self
from src.sparp import SPARP, StopConditions, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPProgressAndStats:
    async def test_progress_bar_displays_truth_on_early_stop(
        self: Self, failing_server: int, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify the UI reflects the object state, regardless of estimate vs truth."""
        cond: StopConditions = StopConditions(stop_on_hard_fail=True)
        sparp: SPARP = SPARP(
            inspect_response=inspect_response,
            stop_conditions=cond,
            show_progress_bar=True,
            concurrency=1,
        )

        result: SparpResult = await sparp._main(req_gen(10, failing_server))

        captured: str = capsys.readouterr().out
        lines: list[str] = [line.strip() for line in captured.split("\r") if line.strip()]
        last_line: str = lines[-1]

        assert f"SUCCESS: {result.stats.success}" in last_line
        assert f"HARD_FAIL: {result.stats.failed}" in last_line
        assert f"PROGRESS: {sparp.dones()}/" in last_line
        assert result.stats.failed > 0

    async def test_progress_bar_last_print_on_exception(
        self: Self, success_server: Dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that the bar displays 0 completions if the inspector crashes on the first request."""

        def crashing_inspector(resp: Any) -> Any:
            raise RuntimeError("UI Crash Test")

        sparp: SPARP = SPARP(
            inspect_response=crashing_inspector,
            show_progress_bar=True,
            concurrency=1,
            progress_bar_requests_threshold=1,
            progress_bar_time_threshold=datetime.timedelta(seconds=0.1),
        )

        with pytest.raises(ExceptionGroup):
            await sparp._main(req_gen(5, success_server["port"]))

        captured: str = capsys.readouterr().out
        lines: list[str] = [line.strip() for line in captured.split("\r") if "PROGRESS:" in line]

        assert len(lines) > 0
        last_line: str = lines[-1]

        assert "SUCCESS: 0" in last_line
        assert "HARD_FAIL: 0" in last_line
        assert "PROGRESS: 0/" in last_line

    async def test_progress_bar_estimated_logic(
        self: Self, capsys: pytest.CaptureFixture[str], success_server: Dict[str, Any]
    ) -> None:
        """Verify the transition from estimate (~) to absolute truth in UI."""
        total: int = 50
        est: int = 100
        sparp: SPARP = SPARP(
            inspect_response=inspect_response,
            show_progress_bar=True,
            concurrency=1,
        )
        result: SparpResult = await sparp._main(
            req_gen(total, success_server["port"]), estimated_input_collection_size=est
        )

        captured: str = capsys.readouterr().out
        lines: list[str] = [line.strip() for line in captured.split("\r") if line.strip()]

        assert any(f"/~{est}" in line for line in lines)
        assert f"{total}/{total}" in lines[-1]
        assert "~" not in lines[-1].split("PROGRESS:")[1]
        assert result.stats.success == total

    async def test_no_output_when_disabled(
        self: Self, success_server: Dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that show_progress_bar=False results in zero stdout usage."""
        sparp: SPARP = SPARP(
            inspect_response=inspect_response,
            show_progress_bar=False,
            progress_bar_requests_threshold=1,
            progress_bar_time_threshold=datetime.timedelta(seconds=0.1),
        )
        await sparp._main(req_gen(1, success_server["port"]))
        captured: str = capsys.readouterr().out
        assert captured == ""
