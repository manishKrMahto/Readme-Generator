from __future__ import annotations

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, JsonDict
from core.backend.agents.utils import md_anchor


class TableOfContentsAgent(BaseAgent[str]):
    name = "table_of_contents"
    version = "1.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"repo_url": ctx.repository.repo_url}

    def _run(self, ctx: AgentContext) -> AgentResult[str]:
        # Dynamic: only include sections that will be present.
        # The orchestrator passes a "sections_present" hint via ctx.repository.last_error? no.
        # Keep deterministic: include everything, but callers can remove empty sections.
        sections = [
            "Tech Stack",
            "Description",
            "Architecture Diagram",
            "API Endpoints",
            "Folder Structure",
            "Installation",
            "Future Improvements",
        ]
        lines = [f"- [{s}](#{md_anchor(s)})" for s in sections]
        return AgentResult(output="\n".join(lines), tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> str:
        return "- [Description](#description)"

