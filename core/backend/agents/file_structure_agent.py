from __future__ import annotations

import re

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext


class FileStructureAgent(BaseAgent[str]):
    name = "file_structure"
    version = "2.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"selected_file_count": len(ctx.files)}

    def _run(self, ctx: AgentContext) -> AgentResult[str]:
        comments = self._infer_file_comments(ctx)
        tree_lines = self._render_commented_tree([f.file_path for f in ctx.files], comments)
        out = "\n".join(["```text", *tree_lines, "```"])
        return AgentResult(output=out, tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> str:
        return "```text\n(empty)\n```"

    _MODEL_CLASS_RE = re.compile(r"^\s*class\s+(?P<name>[A-Za-z_]\w*)\s*\(\s*models\.Model\s*\)\s*:", re.M)
    _DRF_RE = re.compile(r"\bAPIView\b|\bViewSet\b|\bModelViewSet\b|\bSerializer\b|\brest_framework\b")

    def _infer_file_comments(self, ctx: AgentContext) -> dict[str, str]:
        """
        Build a 1-line purpose comment for each file based on filename + lightweight parsing.
        """
        by_path: dict[str, str] = {}

        # Pre-index file chunks by file_path (FILE chunks include full content).
        file_chunk_by_path: dict[str, str] = {}
        for ch in ctx.chunks:
            if ch.chunk_type != "file":
                continue
            fp = (ch.file.file_path or "").replace("\\", "/")
            file_chunk_by_path[fp] = ch.content or ""

        for f in ctx.files:
            fp = (f.file_path or "").replace("\\", "/")
            name = (f.file_name or "").lower()
            content = file_chunk_by_path.get(fp, "")

            if name == "models.py":
                entities = [m.group("name") for m in self._MODEL_CLASS_RE.finditer(content)]
                if entities:
                    by_path[fp] = f"Defines {', '.join(entities[:6])} models"
                else:
                    by_path[fp] = "Defines Django ORM models"
            elif name == "views.py":
                if self._DRF_RE.search(content):
                    by_path[fp] = "Implements API views / viewsets (DRF patterns)"
                else:
                    by_path[fp] = "Implements request handlers and view logic"
            elif name == "urls.py":
                by_path[fp] = "URL routing and route definitions"
            elif name == "admin.py":
                by_path[fp] = "Django admin registrations and configuration"
            elif name == "apps.py":
                by_path[fp] = "Django app configuration"
            elif name == "forms.py":
                by_path[fp] = "Form definitions and validation"
            elif name == "serializers.py":
                by_path[fp] = "API serializers (request/response schemas)"
            elif name == "signals.py":
                by_path[fp] = "Signal handlers (model lifecycle hooks)"
            elif name in {"tests.py", "conftest.py"} or fp.startswith("tests/") or "/tests/" in fp:
                by_path[fp] = "Automated tests"
            elif name == "settings.py":
                by_path[fp] = "Application settings and configuration"
            elif name == "manage.py":
                by_path[fp] = "Django management entrypoint"
            elif name == "requirements.txt":
                by_path[fp] = "Python dependencies"
            elif "migrations/" in fp:
                by_path[fp] = "Database migration"
            elif "management/commands/" in fp:
                by_path[fp] = "Custom management command"
            elif "vectorstore" in fp.lower() or "embedding" in fp.lower():
                by_path[fp] = "Vector store / embedding utilities"
            else:
                by_path[fp] = "Source file"

        return by_path

    def _render_commented_tree(self, file_paths: list[str], comments: dict[str, str]) -> list[str]:
        """
        Produce a directory tree with inline `# comments` per file.
        """
        paths = sorted({(p or "").replace("\\", "/").strip("/") for p in file_paths if p})
        if not paths:
            return ["(empty)"]

        # Build nested dict tree.
        root: dict = {}
        for p in paths:
            parts = p.split("/")
            cur = root
            for i, part in enumerate(parts):
                cur = cur.setdefault(part, {} if i < len(parts) - 1 else None)

        def render(node: dict, prefix: str = "") -> list[str]:
            entries = list(node.items())
            out: list[str] = []
            for idx, (name, child) in enumerate(entries):
                last = idx == len(entries) - 1
                branch = "└── " if last else "├── "
                if child is None:
                    # file
                    full = current_path_stack + [name]
                    fp = "/".join(full)
                    c = comments.get(fp, "")
                    suffix = f"  # {c}" if c else ""
                    out.append(prefix + branch + name + suffix)
                else:
                    out.append(prefix + branch + name + "/")
                    new_prefix = prefix + ("    " if last else "│   ")
                    # recurse with path stack
                    current_path_stack.append(name)
                    out.extend(render(child, new_prefix))
                    current_path_stack.pop()
            return out

        current_path_stack: list[str] = []
        return render(root, "")

