from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TreeRenderConfig:
    max_lines: int = 400
    indent: str = "  "


def build_tree(file_paths: list[str]) -> dict:
    root: dict = {}
    for p in sorted({fp.strip("/") for fp in file_paths if fp}):
        parts = [part for part in p.split("/") if part]
        if not parts:
            continue
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault(parts[-1], None)
    return root


def filter_paths_excluding_large_subtrees(
    paths_with_sizes: list[tuple[str, int]],
    large_threshold_bytes: int,
) -> list[str]:
    excluded_dir_prefixes: set[str] = set()
    for path, size in paths_with_sizes:
        if size <= large_threshold_bytes:
            continue
        parts = [p for p in path.split("/") if p]
        if len(parts) <= 1:
            continue
        parent = "/".join(parts[:-1])
        excluded_dir_prefixes.add(parent)

    out: list[str] = []
    for path, _ in paths_with_sizes:
        skip = any(path == ex or path.startswith(ex + "/") for ex in excluded_dir_prefixes)
        if not skip:
            out.append(path)
    return out


def render_tree_box_drawing(tree: dict, max_lines: int = 800) -> str:
    lines: list[str] = []

    def walk(node: dict, prefix: str) -> None:
        if len(lines) >= max_lines:
            return
        keys = sorted(node.keys())
        for i, name in enumerate(keys):
            if len(lines) >= max_lines:
                return
            is_last = i == len(keys) - 1
            connector = "└───" if is_last else "├───"
            lines.append(f"{prefix}{connector}{name}")
            child = node[name]
            if isinstance(child, dict) and child:
                ext = "    " if is_last else "│   "
                walk(child, prefix + ext)

    walk(tree, "")
    if len(lines) >= max_lines:
        lines = lines[: max_lines - 1] + ["… (truncated)"]
    return "\n".join(lines)


def iter_directory_paths_from_tree(tree: dict, prefix: str = "") -> list[str]:
    out: list[str] = []
    for name in sorted(tree.keys()):
        child = tree[name]
        path = f"{prefix}/{name}" if prefix else name
        if isinstance(child, dict):
            out.append(path)
            out.extend(iter_directory_paths_from_tree(child, path))
    return out

