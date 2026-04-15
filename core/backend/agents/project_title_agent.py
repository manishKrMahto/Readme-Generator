from __future__ import annotations

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext
from core.backend.agents.utils import humanize_repo_title, repo_name_from_url


class ProjectTitleAgent(BaseAgent[str]):
    name = "project_title"
    version = "1.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"repo_url": ctx.repository.repo_url}

    def _run(self, ctx: AgentContext) -> AgentResult[str]:
        slug = repo_name_from_url(ctx.repository.repo_url)
        title = humanize_repo_title(slug)
        return AgentResult(output=title, tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> str:
        return "Project"

