from __future__ import annotations

import re

from django.conf import settings

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, LlmUsage


class ProjectDescriptionAgent(BaseAgent[dict]):
    """
    Produces:
    - description (markdown)
    - architecture_diagram (mermaid, optional)
    - api_endpoints (best-effort list, optional)
    """

    name = "project_description"
    version = "2.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {
            "selected_file_count": len(ctx.files),
            "chunk_count": len(ctx.chunks),
            "has_existing_readme": bool(ctx.existing_readme_text),
        }

    def _run(self, ctx: AgentContext) -> AgentResult[dict]:
        # Deterministic extraction first (MANDATORY for accuracy / no generic fallback).
        extracted = self._extract_repo_facts(ctx)
        description = self._render_description(extracted)
        architecture = self._render_architecture_mermaid(extracted)

        out = {"description": description, "architecture_diagram": architecture, "api_endpoints": []}

        # Optional LLM: only for polishing phrasing, never to invent facts.
        api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        model = getattr(settings, "OPENAI_MODEL", "") or ""
        if not api_key or not model:
            return AgentResult(output=out, tokens_used=0)

        try:
            import json
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            system = (
                "You improve a README Description section. "
                "You MUST stay strictly within the provided facts; do not add features or endpoints "
                "not explicitly supported. Return ONLY valid JSON: "
                "{\"description\": string, \"architecture_diagram\": string}."
            )
            user_payload = {
                "repo_url": ctx.repository.repo_url,
                "facts": extracted,
                "draft_description_markdown": description,
                "draft_architecture_mermaid": architecture,
            }
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.1,
            )
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            usage = getattr(resp, "usage", None)
            llm_usage = LlmUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            )
            from core.backend.monitoring import log_llm_call

            log_llm_call(
                monitor_id=ctx.monitor.id,
                agent=self.name,
                model=model,
                input_prompt=f"SYSTEM:\\n{system}\\n\\nUSER(JSON):\\n{json.dumps(user_payload, ensure_ascii=False)}",
                output_response=raw,
                input_tokens=llm_usage.input_tokens,
                output_tokens=llm_usage.output_tokens,
            )

            improved_desc = (data.get("description") or "").strip()
            improved_arch = (data.get("architecture_diagram") or "").strip()
            if improved_desc:
                out["description"] = improved_desc
            if improved_arch:
                out["architecture_diagram"] = improved_arch
            return AgentResult(output=out, tokens_used=llm_usage.total_tokens, llm_usage=llm_usage)
        except Exception:
            # Still return deterministic output (and BaseAgent will log the exception).
            return AgentResult(output=out, tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> dict:
        extracted = self._extract_repo_facts(ctx)
        return {
            "description": self._render_description(extracted),
            "architecture_diagram": self._render_architecture_mermaid(extracted),
            "api_endpoints": [],
        }

    def _extract_repo_facts(self, ctx: AgentContext) -> dict:
        apps = self._detect_django_apps(ctx)
        model_entities = self._extract_django_models(ctx)
        view_signals = self._extract_view_signals(ctx)
        urls = self._extract_url_patterns(ctx)
        has_admin = any((f.file_name or "").lower() == "admin.py" for f in ctx.files) or any(
            (f.file_path or "").replace("\\", "/").endswith("/admin.py") for f in ctx.files
        )
        embeddings = self._detect_embeddings(ctx)

        return {
            "apps": sorted(apps),
            "model_entities": {k: sorted(v) for k, v in sorted(model_entities.items())},
            "view_signals": view_signals,
            "url_patterns_sample": urls[:40],
            "has_admin": has_admin,
            "has_embeddings": embeddings["has_embeddings"],
            "embeddings_signals": embeddings["signals"],
        }

    def _detect_django_apps(self, ctx: AgentContext) -> set[str]:
        apps: set[str] = set()
        for f in ctx.files:
            p = (f.file_path or "").replace("\\", "/").strip("/")
            parts = p.split("/")
            if len(parts) >= 2 and parts[1] in {"models.py", "views.py", "urls.py", "apps.py", "admin.py"}:
                apps.add(parts[0])
        # common non-app folders
        for drop in {"static", "templates", "media", "utils"}:
            apps.discard(drop)
        return apps

    _MODEL_CLASS_RE = re.compile(r"^\s*class\s+(?P<name>[A-Za-z_]\w*)\s*\(\s*models\.Model\s*\)\s*:", re.M)

    def _extract_django_models(self, ctx: AgentContext) -> dict[str, set[str]]:
        by_app: dict[str, set[str]] = {}
        for ch in ctx.chunks:
            fp = (ch.file.file_path or "").replace("\\", "/")
            if not fp.endswith("models.py"):
                continue
            app = fp.split("/", 1)[0] if "/" in fp else ""
            found = {m.group("name") for m in self._MODEL_CLASS_RE.finditer(ch.content or "")}
            if found:
                by_app.setdefault(app or "root", set()).update(found)
        return by_app

    def _extract_view_signals(self, ctx: AgentContext) -> dict:
        text = "\n".join([c.content[:8000] for c in ctx.chunks if (c.file.file_path or "").endswith("views.py")])
        signals = {
            "auth": bool(re.search(r"\blogin_required\b|\bLoginView\b|\blogout\b|\bauthenticate\b", text)),
            "crud": bool(re.search(r"\bCreateView\b|\bUpdateView\b|\bDeleteView\b|\bModelViewSet\b", text)),
            "drf": bool(re.search(r"\bAPIView\b|\bViewSet\b|\brest_framework\b", text)),
            "forms": bool(re.search(r"\bforms\.Form\b|\bModelForm\b", text)),
        }
        return signals

    _PATH_RE = re.compile(r"""path\(\s*["'](?P<route>[^"']+)["']""")

    def _extract_url_patterns(self, ctx: AgentContext) -> list[str]:
        out: list[str] = []
        for ch in ctx.chunks:
            fp = (ch.file.file_path or "").replace("\\", "/")
            if not fp.endswith("urls.py"):
                continue
            for m in self._PATH_RE.finditer(ch.content or ""):
                out.append(m.group("route"))
        # Always include admin if it exists in a Django project.
        if any("admin/" in r for r in out) is False:
            # We can't prove it, but core projects often have it; keep only if repo has Django signals.
            if any((f.file_name or "").lower() == "manage.py" for f in ctx.files):
                out.append("admin/")
        return out

    def _detect_embeddings(self, ctx: AgentContext) -> dict:
        signals: list[str] = []
        for f in ctx.files:
            p = (f.file_path or "").replace("\\", "/").lower()
            if "vectorstore" in p or "embedding" in p or "embeddings" in p:
                signals.append(p)
        for ch in ctx.chunks[:50]:
            t = (ch.content or "").lower()
            if "embedding" in t or "vectorstore" in t:
                signals.append((ch.file.file_path or "").replace("\\", "/"))
        return {"has_embeddings": bool(signals), "signals": sorted(set(signals))[:10]}

    def _render_description(self, facts: dict) -> str:
        apps = facts.get("apps") or []
        model_entities = facts.get("model_entities") or {}
        view_signals = facts.get("view_signals") or {}
        has_embeddings = bool(facts.get("has_embeddings"))
        url_sample = facts.get("url_patterns_sample") or []
        url_sample = [u for u in url_sample if isinstance(u, str) and u.strip()]

        # Determine a product-style label based on modules/entities.
        all_entities = {e for ents in model_entities.values() for e in ents}
        flavor = "web application"
        if any("blog" in a.lower() for a in apps) or {"Blog", "Post", "Comment"} & set(all_entities):
            flavor = "blog platform"
        elif any("dashboard" in a.lower() for a in apps):
            flavor = "dashboard-driven web app"

        lines: list[str] = []
        lines.append(f"This repository appears to be a **Django {flavor}** organized into modular apps.")

        lines.append("")
        lines.append("### What this repo does")
        what: list[str] = []
        if apps:
            what.append(f"Implements a Django project split into **{len(apps)} app(s)**: " + ", ".join(f"`{a}`" for a in apps[:12]))
        if model_entities:
            # Highlight a few entities to make this concrete.
            entity_flat = sorted({e for ents in model_entities.values() for e in ents})
            if entity_flat:
                what.append("Defines persistent data models (Django ORM), e.g. " + ", ".join(f"`{e}`" for e in entity_flat[:10]))
        if view_signals.get("drf"):
            what.append("Exposes an API surface using **Django REST Framework** patterns (APIView/ViewSet detected)")
        else:
            what.append("Serves web pages using Django views/templates (standard routing via `urls.py` detected)")
        if facts.get("has_admin"):
            what.append("Includes **Django Admin** configuration (`admin.py` present) for managing data")
        if has_embeddings:
            what.append("Contains embedding/vectorstore-related code signals (AI/semantic utilities present)")
        lines.extend([f"- {w}" for w in what if w])

        if apps:
            lines.append("")
            lines.append("### Core modules")
            for a in apps:
                ents = model_entities.get(a) or []
                if ents:
                    lines.append(f"- **{a}**: data models like {', '.join(f'`{x}`' for x in ents[:8])}")
                else:
                    lines.append(f"- **{a}**")

        lines.append("")
        lines.append("### Core features (inferred from code)")
        caps: list[str] = []
        if view_signals.get("auth"):
            caps.append("Authentication/session flows (login/logout or auth middleware detected)")
        if view_signals.get("crud"):
            caps.append("CRUD-style operations for primary entities (create/update/delete patterns detected)")
        if facts.get("has_admin"):
            caps.append("Django Admin for back-office management (`admin.py` present)")
        if view_signals.get("drf"):
            caps.append("API layer using Django REST Framework patterns (APIView/ViewSet detected)")
        if has_embeddings:
            caps.append("Vector embeddings / semantic utilities (embedding/vectorstore signals detected)")
        if not caps:
            caps.append("Standard Django request/response views and routing via `urls.py`")
        lines.extend([f"- {c}" for c in caps])

        lines.append("")
        lines.append("### How it works (high-level)")
        how: list[str] = []
        how.append("Incoming HTTP requests are routed by **Django URL patterns** (`urls.py`) to view functions/classes.")
        if view_signals.get("drf"):
            how.append("API requests are handled by DRF views/viewsets, which serialize/validate data and return JSON responses.")
        how.append("Business logic typically reads/writes **Django ORM models**; persistence is handled by the configured database.")
        if facts.get("has_admin"):
            how.append("Administrative operations are available via Django Admin (if enabled in URL config).")
        if has_embeddings:
            how.append("Embedding/vectorstore modules (where used) support semantic or vector-based workflows.")
        lines.extend([f"- {h}" for h in how if h])

        if url_sample:
            lines.append("")
            lines.append("### Routes / endpoints (sample)")
            lines.append("*(Extracted from `urls.py` patterns; this is a best-effort sample, not a full inventory.)*")
            for r in url_sample[:20]:
                lines.append(f"- `{r}`")

        if has_embeddings:
            sigs = facts.get("embeddings_signals") or []
            if sigs:
                lines.append("")
                lines.append("### AI / semantic search signals")
                lines.append("- Detected embedding/vectorstore-related modules:")
                for s in sigs:
                    lines.append(f"  - `{s}`")

        return "\n".join(lines).strip()

    def _render_architecture_mermaid(self, facts: dict) -> str:
        apps = facts.get("apps") or []
        if not apps:
            return ""
        # Slightly richer, still factual diagram.
        # Use safe node ids (mermaid doesn't like hyphens/spaces).
        def _nid(name: str) -> str:
            return "app_" + re.sub(r"[^A-Za-z0-9_]", "_", name)

        app_nodes = []
        app_edges = []
        for a in apps[:12]:
            nid = _nid(a)
            app_nodes.append(f'  {nid}["{a} app"]')
            app_edges.append(f"  views --> {nid}")

        return "\n".join(
            [
                "```mermaid",
                "flowchart LR",
                '  web["Client / HTTP"] --> urls["Django URL routing\\n(`urls.py`)"]',
                '  urls --> views["Views / Controllers\\n(Django views or DRF)"]',
                '  views --> orm["Django ORM"]',
                '  orm --> db[("Database")]',
                *app_nodes,
                *app_edges,
                "  views --> templates[\"Templates / HTML (if used)\"]",
                "  views --> serializers[\"Serializers (if DRF used)\"]",
                "```",
            ]
        )

