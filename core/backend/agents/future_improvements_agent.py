from __future__ import annotations

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, JsonDict


class FutureImprovementsAgent(BaseAgent[str]):
    name = "future_improvements"
    version = "1.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"file_count": len(ctx.files)}

    def _run(self, ctx: AgentContext) -> AgentResult[str]:
        suggestions: list[str] = []

        # Repo hygiene
        has_ci = any(p.replace("\\", "/").startswith(".github/workflows") for p in ctx.folder_paths)
        if not has_ci:
            suggestions.append("Add CI via GitHub Actions (lint + tests) to keep the project merge-ready.")

        # Dependency pinning hints
        has_req = any((f.file_name or "").lower() == "requirements.txt" for f in ctx.files)
        has_pyproject = any((f.file_name or "").lower() == "pyproject.toml" for f in ctx.files)
        if has_req and not has_pyproject:
            suggestions.append("Consider adding `pyproject.toml` for modern packaging and tooling configuration.")

        # Docs
        if not any((f.file_name or "").lower() in {"readme.md", "readme"} for f in ctx.files):
            suggestions.append("Add project documentation: usage examples, configuration, and deployment notes.")

        if not suggestions:
            suggestions = [
                "Add automated tests and a minimal CI pipeline.",
                "Document configuration options and common workflows.",
                "Add deployment instructions for the primary environment.",
            ]

        return AgentResult(output="\n".join([f"- {s}" for s in suggestions]), tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> str:
        return "- Add automated tests and CI."

