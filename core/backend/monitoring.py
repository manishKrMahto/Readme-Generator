from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.backend.agents.utils import estimate_cost_usd
from core.backend.models import ReadmeGenerationMonitor


def _trim_text(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n\n...(trimmed)..."


@dataclass(frozen=True)
class LlmCall:
    agent: str
    model: str
    input_prompt: str
    output_response: str
    input_tokens: int
    output_tokens: int
    timestamp: str

    @property
    def total_tokens(self) -> int:
        return int(self.input_tokens) + int(self.output_tokens)


def log_agent_execution(
    *,
    monitor_id,
    agent_name: str,
    status: str,
    execution_time_ms: int,
    output: Any,
    tokens_used: int = 0,
    error_message: str = "",
) -> None:
    """
    Append/update per-agent execution summary inside a single monitor row.
    """
    with transaction.atomic():
        m = ReadmeGenerationMonitor.objects.select_for_update().get(id=monitor_id)
        logs = dict(m.agent_logs or {})
        logs[agent_name] = {
            "status": status,
            "execution_time_ms": int(execution_time_ms),
            "tokens_used": int(tokens_used or 0),
            "output": output,
            "error_message": error_message,
        }
        m.agent_logs = logs
        m.save(update_fields=["agent_logs", "updated_at"])


def log_llm_call(
    *,
    monitor_id,
    agent: str,
    model: str,
    input_prompt: str,
    output_response: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """
    Stores every LLM call (trimmed for performance) and updates token + cost rollups.
    Returns the computed cost for this call.
    """
    now = timezone.now().isoformat()
    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)
    cost = estimate_cost_usd(model, input_tokens, output_tokens)

    entry = {
        "agent": agent,
        "model": model,
        "input_prompt": _trim_text(input_prompt, 12_000),
        "output_response": _trim_text(output_response, 12_000),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": str(cost),
        "timestamp": now,
    }

    with transaction.atomic():
        m = ReadmeGenerationMonitor.objects.select_for_update().get(id=monitor_id)
        calls = list(m.llm_calls or [])
        calls.append(entry)
        m.llm_calls = calls[-200:]  # keep bounded
        m.llm_call_count = int(m.llm_call_count or 0) + 1

        m.total_input_tokens = int(m.total_input_tokens or 0) + input_tokens
        m.total_output_tokens = int(m.total_output_tokens or 0) + output_tokens
        m.total_tokens = int(m.total_tokens or 0) + input_tokens + output_tokens
        m.total_cost_usd = (m.total_cost_usd or Decimal("0")) + cost
        m.save(
            update_fields=[
                "llm_calls",
                "llm_call_count",
                "total_input_tokens",
                "total_output_tokens",
                "total_tokens",
                "total_cost_usd",
                "updated_at",
            ]
        )

    return cost


def finalize_monitoring(
    *,
    monitor_id,
    status: str,
    readme_content: str = "",
    readme_sections: dict | None = None,
    detected_tech_stack: dict | None = None,
    total_files_processed: int = 0,
    total_chunks_created: int = 0,
    error_message: str = "",
    failed_step: str = "",
    started_perf_counter: float | None = None,
) -> None:
    with transaction.atomic():
        m = ReadmeGenerationMonitor.objects.select_for_update().get(id=monitor_id)
        m.status = status
        m.completed_at = timezone.now()
        if started_perf_counter is not None:
            m.total_execution_time_ms = int((time.perf_counter() - started_perf_counter) * 1000)
        m.readme_content = readme_content or ""
        m.readme_sections = readme_sections or {}
        m.detected_tech_stack = detected_tech_stack or {}
        m.total_files_processed = int(total_files_processed or 0)
        m.total_chunks_created = int(total_chunks_created or 0)
        m.error_message = error_message or ""
        m.failed_step = failed_step or ""

        # If agents reported token usage but no structured LLM-call logging occurred,
        # keep the monitor useful by rolling up total tokens from per-agent logs.
        #
        # This happens when an agent returns tokens_used but doesn't call log_llm_call(),
        # or when the UI only cares about totals (not call-by-call traces).
        if int(getattr(m, "total_tokens", 0) or 0) == 0:
            try:
                logs = m.agent_logs or {}
                inferred_total = 0
                if isinstance(logs, dict):
                    for v in logs.values():
                        if isinstance(v, dict):
                            inferred_total += int(v.get("tokens_used", 0) or 0)
                if inferred_total > 0:
                    m.total_tokens = inferred_total
            except Exception:
                pass

        m.save(
            update_fields=[
                "status",
                "completed_at",
                "total_execution_time_ms",
                "readme_content",
                "readme_sections",
                "detected_tech_stack",
                "total_files_processed",
                "total_chunks_created",
                "error_message",
                "failed_step",
                "total_tokens",
                "updated_at",
            ]
        )

