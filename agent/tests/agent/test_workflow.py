"""Tests for WorkflowEngine pipeline (pygentic-ai user_assistant_graph)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.workflows.agent_workflow import WorkflowEngine, _build_history


@pytest.fixture
def engine() -> WorkflowEngine:
    return WorkflowEngine()


class TestBuildHistory:
    def test_empty_history_returns_empty_list(self) -> None:
        assert _build_history([]) == []

    def test_user_messages_are_included(self) -> None:
        history = [{"role": "user", "content": "Hello"}]
        result = _build_history(history)
        assert len(result) == 1

    def test_assistant_messages_are_included(self) -> None:
        history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ]
        result = _build_history(history)
        # Both user and assistant turns are seeded into the history
        assert len(result) == 2

    def test_mixed_history_preserves_order(self) -> None:
        history = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Reply"},
            {"role": "user", "content": "Second"},
        ]
        result = _build_history(history)
        assert len(result) == 3


class TestWorkflowEngineRun:
    async def test_run_returns_graph_output_as_string(self, engine: WorkflowEngine) -> None:
        mock_result = MagicMock()
        mock_result.output = "Formatted response"

        with patch(
            "app.agent.workflows.agent_workflow.user_assistant_graph.run",
            AsyncMock(return_value=mock_result),
        ):
            result = await engine.run(
                user_id=uuid4(),
                message="How was my sleep last week?",
                history=[],
            )

        assert result == "Formatted response"

    async def test_run_converts_output_to_string(self, engine: WorkflowEngine) -> None:
        mock_result = MagicMock()
        mock_result.output = 42  # non-string output

        with patch(
            "app.agent.workflows.agent_workflow.user_assistant_graph.run",
            AsyncMock(return_value=mock_result),
        ):
            result = await engine.run(user_id=uuid4(), message="Test", history=[])

        assert result == "42"
        assert isinstance(result, str)

    async def test_run_passes_message_to_graph(self, engine: WorkflowEngine) -> None:
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.output = "OK"
        graph_run = AsyncMock(return_value=mock_result)

        with patch("app.agent.workflows.agent_workflow.user_assistant_graph.run", graph_run):
            await engine.run(user_id=user_id, message="My message", history=[])

        call_kwargs = graph_run.call_args.kwargs
        deps = call_kwargs["deps"]
        assert deps["message"] == "My message"

    async def test_run_passes_chat_history_to_graph(self, engine: WorkflowEngine) -> None:
        mock_result = MagicMock()
        mock_result.output = "OK"
        graph_run = AsyncMock(return_value=mock_result)

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        with patch("app.agent.workflows.agent_workflow.user_assistant_graph.run", graph_run):
            await engine.run(user_id=uuid4(), message="Follow-up", history=history)

        deps = graph_run.call_args.kwargs["deps"]
        assert "chat_history" in deps
        assert len(deps["chat_history"]) == 2  # both user and assistant turns seeded

    async def test_run_passes_agent_router_guardrails_in_deps(self, engine: WorkflowEngine) -> None:
        mock_result = MagicMock()
        mock_result.output = "OK"
        graph_run = AsyncMock(return_value=mock_result)

        with patch("app.agent.workflows.agent_workflow.user_assistant_graph.run", graph_run):
            await engine.run(user_id=uuid4(), message="Test", history=[])

        deps = graph_run.call_args.kwargs["deps"]
        assert "agent" in deps
        assert "router" in deps
        assert "guardrails" in deps

    async def test_run_passes_language_in_deps(self, engine: WorkflowEngine) -> None:
        from app.schemas.language import Language

        mock_result = MagicMock()
        mock_result.output = "OK"
        graph_run = AsyncMock(return_value=mock_result)

        with patch("app.agent.workflows.agent_workflow.user_assistant_graph.run", graph_run):
            await engine.run(user_id=uuid4(), message="Test", history=[], language=Language.english)

        deps = graph_run.call_args.kwargs["deps"]
        assert "language" in deps
        assert deps["language"] == "english"


class TestWorkflowEngineSummarize:
    async def test_returns_summary_string(self, engine: WorkflowEngine) -> None:
        summary_result = MagicMock()
        summary_result.output = "Summary of the conversation."

        mock_summarizer = MagicMock()
        mock_summarizer.run = AsyncMock(return_value=summary_result)

        with patch("pydantic_ai.Agent", return_value=mock_summarizer):
            result = await engine.summarize(
                [
                    {"role": "user", "content": "How many steps?"},
                    {"role": "assistant", "content": "You walked 8000 steps."},
                ]
            )

        assert result == "Summary of the conversation."

    async def test_formats_transcript_correctly(self, engine: WorkflowEngine) -> None:
        summary_result = MagicMock()
        summary_result.output = "OK"

        mock_summarizer = MagicMock()
        mock_summarizer.run = AsyncMock(return_value=summary_result)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        with patch("pydantic_ai.Agent", return_value=mock_summarizer):
            await engine.summarize(messages)

        prompt = mock_summarizer.run.call_args[0][0]
        assert "USER: Hello" in prompt
        assert "ASSISTANT: Hi there" in prompt
