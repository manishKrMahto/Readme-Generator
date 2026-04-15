from __future__ import annotations

from core.backend.agents.component_aggregator import AggregatedComponents


class ReadmeRenderer:
    def render(self, c: AggregatedComponents) -> str:
        parts: list[str] = []
        parts.extend([f"# {c.title or 'Project'}", ""])

        if c.table_of_contents:
            parts.extend(["## Table of Contents", "", c.table_of_contents, ""])

        if c.tech_stack and any(v for v in c.tech_stack.values()):
            parts.extend(["## Tech Stack", "", self._render_tech_stack(c.tech_stack), ""])

        if c.description:
            parts.extend(["## Description", "", c.description, ""])

        if c.architecture_diagram:
            parts.extend(["## Architecture Diagram", "", c.architecture_diagram, ""])

        if c.api_endpoints:
            parts.extend(["## API Endpoints", "", self._render_api_endpoints(c.api_endpoints), ""])

        if c.file_structure:
            parts.extend(["## Folder Structure", "", c.file_structure, ""])

        if c.installation:
            parts.extend(["## Installation", "", c.installation, ""])

        if c.future_improvements:
            parts.extend(["## Future Improvements", "", c.future_improvements, ""])

        # Trim trailing whitespace-only lines
        while parts and not parts[-1].strip():
            parts.pop()
        return "\n".join(parts) + "\n"

    def _render_tech_stack(self, tech: dict) -> str:
        backend = tech.get("backend") or ""
        frontend = tech.get("frontend") or ""
        database = tech.get("database") or ""
        ai_ml = tech.get("ai_ml") or ""
        devops = tech.get("devops") or []
        languages = tech.get("languages") or []

        lines: list[str] = []
        if backend:
            if backend == "Django":
                lines.append("- **Backend**: Django (Python-based web framework)")
            elif backend == "FastAPI":
                lines.append("- **Backend**: FastAPI (async Python API framework)")
            elif backend == "Flask":
                lines.append("- **Backend**: Flask (lightweight Python web framework)")
            else:
                lines.append(f"- **Backend**: {backend}")
        if frontend:
            lines.append(f"- **Frontend**: {frontend}")
        if database:
            if database == "SQLite":
                lines.append("- **Database**: SQLite (default Django DB in development)")
            elif database == "ORM":
                lines.append("- **Database**: Django ORM (database engine inferred from configuration)")
            else:
                lines.append(f"- **Database**: {database}")
        if ai_ml:
            lines.append(f"- **AI/ML**: {ai_ml}")
        if devops:
            lines.append(f"- **DevOps**: {', '.join(devops)}")
        if languages:
            lines.append(f"- **Languages**: {', '.join(languages)}")
        return "\n".join(lines) if lines else "- *(Not detected)*"

    def _render_api_endpoints(self, eps: list[dict]) -> str:
        # Keep deterministic, path-first view.
        lines = ["| Path | Name | Description |", "|---|---|---|"]
        for e in eps:
            p = str(e.get("path") or "") or "-"
            n = str(e.get("name") or "") or "-"
            d = str(e.get("description") or "") or "-"
            lines.append(f"| `{p}` | `{n}` | {d} |")
        return "\n".join(lines)

