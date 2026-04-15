from __future__ import annotations

import re

from core.backend.agents.base import AgentResult, BaseAgent
from core.backend.agents.types import AgentContext, JsonDict


class InstallationInstructionsAgent(BaseAgent[str]):
    name = "installation_instructions"
    version = "2.0"

    def build_input_log(self, ctx: AgentContext) -> dict:
        return {"repo_url": ctx.repository.repo_url}

    def _run(self, ctx: AgentContext) -> AgentResult[str]:
        names = {(f.file_name or "").lower() for f in ctx.files}
        paths = {(f.file_path or "").replace("\\", "/") for f in ctx.files}

        repo_url = (ctx.repository.repo_url or "").strip()
        project_dir = (repo_url.rstrip("/").split("/")[-1] or "project").replace(".git", "")

        py_ver = self._detect_python_version(ctx)
        env_keys = self._detect_env_keys(ctx)
        has_env = bool(env_keys) or any(n in names for n in {".env", ".env.example", ".env_example"})

        if "manage.py" in names:
            guide = []
            guide.append("### Installation Guide")
            guide.append("")
            guide.append("1. **Install Python**")
            guide.append(
                f"   - Recommended: **Python {py_ver}+**" if py_ver else "   - Recommended: **Python 3.9+**"
            )
            guide.append("   - Download: `https://www.python.org/downloads/`")
            guide.append("")
            guide.append("   Verify:")
            guide.append("")
            guide.append("```bash")
            guide.append("python --version")
            guide.append("```")
            guide.append("")
            guide.append("2. **Clone the repository**")
            guide.append("")
            guide.append("```bash")
            guide.append(f"git clone {repo_url}")
            guide.append(f"cd {project_dir}")
            guide.append("```")
            guide.append("")
            guide.append("3. **Create a virtual environment**")
            guide.append("")
            guide.append("```bash")
            guide.append("python -m pip install --upgrade pip")
            guide.append("python -m venv .venv")
            guide.append("```")
            guide.append("")
            guide.append("   Activate it:")
            guide.append("")
            guide.append("   **Windows (PowerShell):**")
            guide.append("")
            guide.append("```bash")
            guide.append(".venv\\Scripts\\Activate.ps1")
            guide.append("```")
            guide.append("")
            guide.append("   **macOS/Linux:**")
            guide.append("")
            guide.append("```bash")
            guide.append("source .venv/bin/activate")
            guide.append("```")
            guide.append("")
            guide.append("4. **Install dependencies**")
            guide.append("")
            guide.append("```bash")
            guide.append("pip install --upgrade pip")
            if "requirements.txt" in names:
                guide.append("pip install -r requirements.txt")
            else:
                guide.append("# If this repo uses pyproject.toml, install via your chosen tool (pip/poetry).")
            guide.append("```")
            guide.append("")
            guide.append("5. **Environment variables**")
            guide.append("")
            if has_env:
                guide.append("   This project likely uses environment variables for secrets/config.")
                guide.append("   Create a `.env` file (or copy from an example) and set values.")
                if env_keys:
                    guide.append("")
                    guide.append("   Detected keys:")
                    for k in env_keys[:20]:
                        guide.append(f"   - `{k}`")
            else:
                guide.append("   No `.env` usage was detected. If you add secrets later, use environment variables.")
            guide.append("")
            guide.append("6. **Run migrations**")
            guide.append("")
            guide.append("```bash")
            guide.append("python manage.py migrate")
            guide.append("```")
            guide.append("")
            guide.append("7. **Start the development server**")
            guide.append("")
            guide.append("```bash")
            guide.append("python manage.py runserver")
            guide.append("```")
            guide.append("")
            guide.append("8. **Access the application**")
            guide.append("")
            guide.append("- App: `http://localhost:8000/`")
            guide.append("- Admin: `http://localhost:8000/admin/`")
            return AgentResult(output="\n".join(guide).strip(), tokens_used=0)

        if "package.json" in names:
            out = "\n".join(
                [
                    "### Installation Guide",
                    "",
                    "1. **Install Node.js (LTS)**: `https://nodejs.org/`",
                    "",
                    "2. **Clone the repository**",
                    "",
                    "```bash",
                    f"git clone {repo_url}",
                    f"cd {project_dir}",
                    "```",
                    "",
                    "3. **Install dependencies**",
                    "",
                    "```bash",
                    "npm install",
                    "```",
                    "",
                    "4. **Run the dev server**",
                    "",
                    "```bash",
                    "npm run start",
                    "```",
                ]
            )
            return AgentResult(output=out, tokens_used=0)

        if "requirements.txt" in names:
            out = "\n".join(
                [
                    "### Installation Guide",
                    "",
                    "1. **Install Python** (recommended 3.9+): `https://www.python.org/downloads/`",
                    "",
                    "2. **Clone the repository**",
                    "",
                    "```bash",
                    f"git clone {repo_url}",
                    f"cd {project_dir}",
                    "```",
                    "",
                    "3. **Create and activate a virtual environment**",
                    "",
                    "```bash",
                    "python -m venv .venv",
                    "```",
                    "",
                    "4. **Install dependencies**",
                    "",
                    "```bash",
                    "pip install --upgrade pip",
                    "pip install -r requirements.txt",
                    "```",
                ]
            )
            return AgentResult(output=out, tokens_used=0)

        if any(p.lower().endswith("/dockerfile") for p in paths) or "dockerfile" in names:
            return AgentResult(
                output="\n".join(
                    [
                        "### Installation Guide (Docker)",
                        "",
                        "1. **Install Docker**: `https://docs.docker.com/get-docker/`",
                        "",
                        "2. **Build the image**",
                        "",
                        "```bash",
                        "docker build -t app .",
                        "```",
                        "",
                        "3. **Run the container**",
                        "",
                        "```bash",
                        "docker run --rm -p 8000:8000 app",
                        "```",
                    ]
                ),
                tokens_used=0,
            )

        return AgentResult(
            output="\n".join(
                [
                    "### Installation Guide",
                    "",
                    "Setup instructions could not be confidently inferred from the repository contents.",
                    "Common next steps:",
                    "- Look for `README.md`, `docs/`, or `Makefile`",
                    "- Check for `requirements.txt`, `pyproject.toml`, or `package.json`",
                ]
            ),
            tokens_used=0,
        )

    def _fallback_output(self, ctx: AgentContext) -> str:
        return "### Installation Guide\n\nSetup instructions could not be inferred."

    def _detect_python_version(self, ctx: AgentContext) -> str | None:
        # Heuristic: pyproject.toml / runtime.txt style.
        for ch in ctx.chunks:
            fp = (ch.file.file_path or "").replace("\\", "/").lower()
            if fp.endswith("pyproject.toml") or fp.endswith("runtime.txt") or fp.endswith(".python-version"):
                m = re.search(r"(\b3\.\d+\b)", ch.content or "")
                if m:
                    return m.group(1)
        return None

    def _detect_env_keys(self, ctx: AgentContext) -> list[str]:
        keys: set[str] = set()
        getenv_re = re.compile(r"""os\.getenv\(\s*["'](?P<k>[A-Z0-9_]+)["']""")
        for ch in ctx.chunks:
            if (ch.file.file_path or "").replace("\\", "/").endswith("settings.py") or (
                ch.file.file_path or ""
            ).endswith(".py"):
                for m in getenv_re.finditer(ch.content or ""):
                    keys.add(m.group("k"))
        return sorted(keys)

