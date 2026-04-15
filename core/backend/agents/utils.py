from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import urlparse


def repo_name_from_url(repo_url: str) -> str:
    """
    Extract the repository slug from a GitHub-style URL.
    Supports https/http/git@ forms and optional `.git`.
    """
    u = (repo_url or "").strip()
    if not u:
        return "Project"

    # git@github.com:owner/repo.git
    if u.startswith("git@") and ":" in u:
        path = u.split(":", 1)[1]
        name = path.rstrip("/").split("/")[-1]
        return name[:-4] if name.lower().endswith(".git") else name

    try:
        parsed = urlparse(u)
        name = (parsed.path or "").rstrip("/").split("/")[-1] or "Project"
        return name[:-4] if name.lower().endswith(".git") else name
    except Exception:
        name = u.rstrip("/").split("/")[-1] or "Project"
        return name[:-4] if name.lower().endswith(".git") else name


_WORD_SPLIT_RE = re.compile(r"[\s_\-\.]+")


def humanize_repo_title(slug: str) -> str:
    """
    Turn `my-awesome_repo` into `My Awesome Repo`.
    """
    s = (slug or "").strip()
    if not s:
        return "Project"
    parts = [p for p in _WORD_SPLIT_RE.split(s) if p]
    if not parts:
        return "Project"
    return " ".join(p[:1].upper() + p[1:] for p in parts)


def md_anchor(text: str) -> str:
    """
    GitHub-like anchor slug (simple/robust, not perfect).
    """
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"-+", "-", t)
    return t.strip("-") or "section"


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """
    Best-effort cost estimate. If unknown model, returns 0.
    Prices are intentionally conservative defaults and can be overridden later.
    """
    m = (model or "").strip()
    if not m:
        return Decimal("0")

    # USD per 1M tokens (Standard pricing).
    # Source: OpenAI API pricing table.
    price_per_1m_in: dict[str, Decimal] = {
        # gpt-4o-mini: $0.15 / 1M input tokens
        "gpt-4o-mini": Decimal("0.15"),
    }
    price_per_1m_out: dict[str, Decimal] = {
        # gpt-4o-mini: $0.60 / 1M output tokens
        "gpt-4o-mini": Decimal("0.60"),
    }
    pin = price_per_1m_in.get(m, Decimal("0"))
    pout = price_per_1m_out.get(m, Decimal("0"))
    cost = (Decimal(input_tokens) * pin + Decimal(output_tokens) * pout) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))

