from __future__ import annotations

import re

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, JsonDict


class ExistingReadmeMergerAgent(BaseAgent[JsonDict]):
    """
    Extract "useful" parts from an existing README and provide merge hints.
    This agent is intentionally conservative and does not attempt complex markdown rewriting.
    """

    name = "existing_readme_merger"
    version = "1.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"has_existing_readme": bool(ctx.existing_readme_text)}

    def _run(self, ctx: AgentContext) -> AgentResult[JsonDict]:
        text = (ctx.existing_readme_text or "").strip()
        if not text:
            return AgentResult(output={"has_readme": False, "kept_sections": {}}, tokens_used=0)

        kept = self._extract_sections(text)
        return AgentResult(output={"has_readme": True, "kept_sections": kept}, tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> JsonDict:
        return {"has_readme": False, "kept_sections": {}}

    def _extract_sections(self, text: str) -> dict[str, str]:
        """
        Keep sections that are typically valuable and not purely duplicative.
        """
        # Simple markdown split on headings.
        heading_re = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
        matches = list(heading_re.finditer(text))
        if not matches:
            return {"raw": text[:8000]}

        def norm(h: str) -> str:
            return re.sub(r"\s+", " ", h.strip().lower())

        useful = {
            "installation",
            "setup",
            "usage",
            "configuration",
            "contributing",
            "license",
            "api",
            "endpoints",
        }

        out: dict[str, str] = {}
        for i, m in enumerate(matches):
            title = m.group(2).strip()
            key = norm(title)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if not body:
                continue
            if any(u in key for u in useful):
                out[title] = body[:8000]
        return out

