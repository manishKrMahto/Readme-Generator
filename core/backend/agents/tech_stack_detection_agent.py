from __future__ import annotations

from dataclasses import dataclass

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, JsonDict


@dataclass(frozen=True)
class TechStackReport:
    backend: str | None = None
    frontend: str | None = None
    database: str | None = None
    ai_ml: str | None = None
    devops: list[str] = None  # type: ignore[assignment]
    languages: list[str] = None  # type: ignore[assignment]

    def to_dict(self) -> JsonDict:
        return {
            "backend": self.backend or "",
            "frontend": self.frontend or "",
            "database": self.database or "",
            "ai_ml": self.ai_ml or "",
            "devops": [x for x in (self.devops or []) if x],
            "languages": [x for x in (self.languages or []) if x],
        }


class TechStackDetectionAgent(BaseAgent[JsonDict]):
    """
    Deterministic, explainable, rule-based stack detection.
    Uses:
    - folder structure (ctx.folder_paths)
    - file names & extensions (ctx.files)
    """

    name = "tech_stack_detection"
    version = "1.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        # Log only aggregates to avoid huge payloads.
        exts = {}
        for f in ctx.files:
            e = (f.extension or "").lower()
            if not e:
                continue
            exts[e] = exts.get(e, 0) + 1
        key_names = sorted({(f.file_name or "").lower() for f in ctx.files})
        return {
            "file_count": len(ctx.files),
            "extensions_top": dict(sorted(exts.items(), key=lambda kv: kv[1], reverse=True)[:15]),
            "has_package_json": "package.json" in key_names,
            "has_requirements_txt": "requirements.txt" in key_names,
            "folder_paths_sample": sorted(ctx.folder_paths)[:80],
        }

    def _run(self, ctx: AgentContext) -> AgentResult[JsonDict]:
        file_names = {(f.file_name or "").lower() for f in ctx.files}
        file_paths = {(f.file_path or "").replace("\\", "/").lower() for f in ctx.files}
        folder_paths = {p.replace("\\", "/").lower().strip("/") for p in ctx.folder_paths}
        exts = {(f.extension or "").lower() for f in ctx.files if (f.extension or "").strip()}

        backend = self._detect_backend(file_names=file_names, file_paths=file_paths)
        frontend = self._detect_frontend(file_names=file_names, file_paths=file_paths, folder_paths=folder_paths)
        database = self._detect_database(ctx, file_names=file_names, file_paths=file_paths, backend=backend)
        ai_ml = self._detect_ai_ml(ctx)
        devops = self._detect_devops(file_names=file_names, file_paths=file_paths, folder_paths=folder_paths)
        languages = self._detect_languages(exts=exts)

        report = TechStackReport(
            backend=backend,
            frontend=frontend,
            database=database,
            ai_ml=ai_ml,
            devops=devops,
            languages=languages,
        )
        return AgentResult(output=report.to_dict(), tokens_used=0)

    def _fallback_output(self, ctx: AgentContext) -> JsonDict:
        return TechStackReport(devops=[], languages=[]).to_dict()

    def _detect_backend(self, *, file_names: set[str], file_paths: set[str]) -> str | None:
        # Django
        if "manage.py" in file_names and any(p.endswith("/settings.py") for p in file_paths):
            return "Django"

        # Flask
        if "app.py" in file_names and "requirements.txt" in file_names:
            return "Flask"

        # FastAPI (best-effort)
        if "main.py" in file_names and any("router" in p or "routers" in p for p in file_paths):
            return "FastAPI"

        return None

    def _detect_frontend(
        self, *, file_names: set[str], file_paths: set[str], folder_paths: set[str]
    ) -> str | None:
        if "package.json" not in file_names:
            return None

        # React heuristics
        if "src" in folder_paths and "public" in folder_paths:
            if any(p.endswith("/src/app.tsx") or p.endswith("/src/app.jsx") for p in file_paths) or any(
                p.endswith("/src/index.tsx") or p.endswith("/src/index.jsx") for p in file_paths
            ):
                return "React"
            return "Node.js"

        # Angular / Vue files
        if "angular.json" in file_names:
            return "Angular"
        if "vue.config.js" in file_names:
            return "Vue.js"

        return "Node.js"

    def _detect_database(
        self, ctx: AgentContext, *, file_names: set[str], file_paths: set[str], backend: str | None
    ) -> str | None:
        # Strong signals from config/deps
        req_text = ""
        for ch in ctx.chunks:
            fp = (ch.file.file_path or "").replace("\\", "/").lower()
            if fp.endswith("requirements.txt"):
                req_text = (ch.content or "").lower()
                break

        if "psycopg" in req_text or "postgres" in req_text:
            return "PostgreSQL"
        if "mysqlclient" in req_text or "pymysql" in req_text:
            return "MySQL"
        if "pymongo" in req_text or "mongodb" in req_text:
            return "MongoDB"

        if "schema.sql" in file_names:
            return "SQL"
        if any(p.endswith("/models.py") for p in file_paths):
            return "ORM"
        if any("mongodb" in p for p in file_paths) or any("mongo" in p for p in file_paths):
            return "MongoDB"
        if backend == "Django":
            return "SQLite"
        return None

    def _detect_devops(
        self, *, file_names: set[str], file_paths: set[str], folder_paths: set[str]
    ) -> list[str]:
        out: list[str] = []
        if "dockerfile" in file_names or any(p.endswith("/dockerfile") for p in file_paths):
            out.append("Docker")
        if ".github/workflows" in folder_paths or any("/.github/workflows/" in p for p in file_paths):
            out.append("GitHub Actions")
        return out

    def _detect_languages(self, *, exts: set[str]) -> list[str]:
        out: list[str] = []
        if "py" in exts:
            out.append("Python")
        if "ts" in exts or "tsx" in exts:
            out.append("TypeScript")
        if "js" in exts or "jsx" in exts:
            out.append("JavaScript")
        if "java" in exts:
            out.append("Java")
        if "go" in exts:
            out.append("Go")
        if "rs" in exts:
            out.append("Rust")
        return out

    def _detect_ai_ml(self, ctx: AgentContext) -> str | None:
        # Deterministic: based on filenames/paths and content keywords.
        signals = []
        for f in ctx.files:
            p = (f.file_path or "").replace("\\", "/").lower()
            if "vectorstore" in p or "embedding" in p or "embeddings" in p:
                signals.append(p)
        for ch in ctx.chunks[:50]:
            t = (ch.content or "").lower()
            if "embedding" in t or "vectorstore" in t:
                signals.append((ch.file.file_path or "").replace("\\", "/").lower())
        return "Vector embeddings" if signals else None

