from __future__ import annotations

import re

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext


class ApiEndpointsAgent(BaseAgent[list[dict]]):
    """
    Deterministically extracts URL routes from Django-style `urls.py`.

    Output schema:
    [{"path": "/blogs/", "name": "blog_list", "description": "Blog-related endpoints"}, ...]
    """

    name = "api_endpoints"
    version = "1.0"

    _PATH_CALL_RE = re.compile(
        r"""path\(\s*["'](?P<route>[^"']+)["']\s*,(?P<rest>[^)]*)\)""", re.MULTILINE
    )
    _NAME_RE = re.compile(r"""name\s*=\s*["'](?P<name>[^"']+)["']""")

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"urls_files": [f.file_path for f in ctx.files if (f.file_path or "").endswith("urls.py")][:20]}

    def _run(self, ctx: AgentContext) -> AgentResult[list[dict]]:
        endpoints: list[dict] = []
        for ch in ctx.chunks:
            fp = (ch.file.file_path or "").replace("\\", "/")
            if not fp.endswith("urls.py"):
                continue

            for m in self._PATH_CALL_RE.finditer(ch.content or ""):
                route = (m.group("route") or "").strip()
                rest = m.group("rest") or ""
                nm = ""
                nm_m = self._NAME_RE.search(rest)
                if nm_m:
                    nm = (nm_m.group("name") or "").strip()

                path = "/" + route.lstrip("/")
                if not path.endswith("/"):
                    path += "/"
                if path.startswith("/admin/"):
                    nm = nm or "admin"
                    desc = "Django admin panel"
                else:
                    desc = self._describe_route(fp, path)
                endpoints.append({"path": path, "name": nm, "description": desc})

        # Common Django admin.
        if any((f.file_name or "").lower() == "manage.py" for f in ctx.files):
            if not any(e["path"].startswith("/admin/") for e in endpoints):
                endpoints.append({"path": "/admin/", "name": "admin", "description": "Django admin panel"})

        # de-dupe by path
        seen: set[str] = set()
        uniq: list[dict] = []
        for e in endpoints:
            p = e.get("path") or ""
            if p in seen:
                continue
            seen.add(p)
            uniq.append(e)

        uniq.sort(key=lambda x: x.get("path") or "")
        return AgentResult(output=uniq[:60], tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> list[dict]:
        return []

    def _describe_route(self, file_path: str, path: str) -> str:
        fp = (file_path or "").lower()
        if "/blogs/" in path or fp.startswith("blogs/"):
            return "Blog-related routes"
        if "/dashboards/" in path or fp.startswith("dashboards/"):
            return "Dashboard routes"
        if "/assignments/" in path or fp.startswith("assignments/"):
            return "Assignments routes"
        if "/api/" in path:
            return "API routes"
        return "Application route"

