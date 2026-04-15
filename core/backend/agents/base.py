from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from core.backend.agents.types import AgentContext, JsonDict, LlmUsage
from core.backend.monitoring import log_agent_execution
from core.backend.models import Repository

TOut = TypeVar("TOut")


@dataclass(frozen=True)
class AgentResult(Generic[TOut]):
    output: TOut
    tokens_used: int = 0
    llm_usage: LlmUsage | None = None


class BaseAgent(Generic[TOut]):
    """
    Service-layer base class for a single, specialized agent.

    - Deterministic agents should return tokens_used=0.
    - LLM-backed agents should return best-effort usage info.
    - This base class appends into the ReadmeGenerationMonitor JSON for every run.
    """

    name: str = "base"
    version: str = "1.0"

    def build_input_log(self, ctx: AgentContext) -> JsonDict:
        # Keep small and safe by default.
        return {"repo_url": ctx.repository.repo_url}

    def build_output_log(self, output: Any) -> JsonDict:
        # Must be JSON-serializable.
        if isinstance(output, dict):
            return output
        return {"value": output}

    def run(self, ctx: AgentContext) -> AgentResult[TOut]:
        start = time.perf_counter()
        tokens_used = 0
        err = ""
        output: TOut
        llm_usage: LlmUsage | None = None

        in_log = self.build_input_log(ctx)
        try:
            result = self._run(ctx)
            output = result.output
            tokens_used = int(result.tokens_used or 0)
            llm_usage = result.llm_usage
            status = "success"
        except Exception as e:
            err = str(e)
            output = self._fallback_output(ctx)  # type: ignore[assignment]
            status = "failed"

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        out_log = self.build_output_log(output)

        # Always log, even on fallback.
        log_agent_execution(
            monitor_id=ctx.monitor.id,
            agent_name=self.name,
            status=status,
            execution_time_ms=elapsed_ms,
            output={"input": in_log, "output": out_log},
            tokens_used=tokens_used,
            error_message=err,
        )

        return AgentResult(output=output, tokens_used=tokens_used, llm_usage=llm_usage)

    def _run(self, ctx: AgentContext) -> AgentResult[TOut]:
        raise NotImplementedError

    def _fallback_output(self, ctx: AgentContext) -> TOut:
        raise NotImplementedError


def normalize_repo_status(repo: Repository, *, failed: bool, error_message: str = "") -> None:
    repo.status = Repository.Status.FAILED if failed else Repository.Status.COMPLETED
    repo.last_error = error_message
    repo.save(update_fields=["status", "last_error", "updated_at"])

