from __future__ import annotations

import json
import logging

from django.conf import settings

from core.backend.models import Repository

logger = logging.getLogger(__name__)


def generate_tagline_and_description(
    repository: Repository,
    tree_text_for_prompt: str,
) -> tuple[str, str]:
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    model = getattr(settings, "OPENAI_MODEL", "") or ""
    if not api_key or not model:
        return _fallback_tagline_and_description(repository, tree_text_for_prompt)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        title = _default_title(repository)
        stack_label = repository.get_tech_stack_display()
        system = (
            "You write README sections for a software repository. "
            "Respond with ONLY valid JSON: {\"tagline\": string, \"description\": string}. "
            "tagline must be a single short sentence (no newline). "
            "description must be Markdown (2–6 short paragraphs) explaining what the project likely does, "
            "who it is for, and how major folders fit together; stay factual and avoid inventing features "
            "not suggested by the tree or tech stack."
        )
        user_payload = {
            "repo_url": repository.repo_url,
            "project_title_guess": title,
            "tech_stack": stack_label,
            "directory_tree_excerpt": tree_text_for_prompt[:24_000],
        }
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        tagline = (data.get("tagline") or "").strip().replace("\n", " ")
        description = (data.get("description") or "").strip()
        if not tagline or not description:
            return _fallback_tagline_and_description(repository, tree_text_for_prompt)
        return tagline, description
    except Exception:
        logger.exception("OpenAI tagline/description failed; using fallback")
        return _fallback_tagline_and_description(repository, tree_text_for_prompt)


def _default_title(repository: Repository) -> str:
    return repository.repo_url.rstrip("/").split("/")[-1] or "Project"


def _fallback_tagline_and_description(
    repository: Repository,
    tree_text_for_prompt: str,
) -> tuple[str, str]:
    title = _default_title(repository)
    stack = repository.get_tech_stack_display()
    tagline = f"{title} — {stack} project (inferred from repository layout)."
    excerpt = tree_text_for_prompt.strip() or "(No tree excerpt available.)"
    description = "\n\n".join(
        [
            f"This repository contains **{title}**. The pipeline detected a primary stack of **{stack}**.",
            "Below is a high-level picture of how the repository is organized. "
            "Use the code structure section for a full directory tree and per-folder notes.",
            f"**Layout excerpt:**\n\n```text\n{excerpt[:6000]}\n```",
        ]
    )
    return tagline, description

