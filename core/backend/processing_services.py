from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from core.backend.models import CodeChunk, FileMetadata, Repository
from core.backend.processing_utils import ParsedSymbol, regex_parse_js_ts

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    pass


@dataclass(frozen=True)
class ParsedFile:
    imports: list[str]
    classes: list[ParsedSymbol]
    functions: list[ParsedSymbol]


class CodeParserService:
    def parse_python(self, source: str) -> ParsedFile:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ParsedFile(imports=[], classes=[], functions=[])

        imports: list[str] = []
        classes: list[ParsedSymbol] = []
        functions: list[ParsedSymbol] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}:{alias.name}" if module else alias.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(
                    ParsedSymbol(
                        kind="class",
                        name=node.name,
                        start_line=getattr(node, "lineno", None),
                        end_line=getattr(node, "end_lineno", None),
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(
                    ParsedSymbol(
                        kind="function",
                        name=node.name,
                        start_line=getattr(node, "lineno", None),
                        end_line=getattr(node, "end_lineno", None),
                        extra={"async": isinstance(node, ast.AsyncFunctionDef)},
                    )
                )

        classes.sort(key=lambda s: s.start_line or 10**9)
        functions.sort(key=lambda s: s.start_line or 10**9)
        return ParsedFile(imports=sorted(set(imports)), classes=classes, functions=functions)

    def parse_other(self, extension: str, source: str) -> ParsedFile:
        ext = (extension or "").lower()
        if ext in {"js", "jsx", "ts", "tsx"}:
            syms = regex_parse_js_ts(source)
            classes = [s for s in syms if s.kind == "class"]
            functions = [s for s in syms if s.kind == "function"]
            return ParsedFile(imports=[], classes=classes, functions=functions)
        return ParsedFile(imports=[], classes=[], functions=[])


class HybridChunkingService:
    def __init__(self, parser: CodeParserService | None = None) -> None:
        self.parser = parser or CodeParserService()

    def build_chunks(self, file_meta: FileMetadata, repo_root: Path) -> list[CodeChunk]:
        abs_path = repo_root / file_meta.file_path
        try:
            source = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ProcessingError(f"Failed reading file: {file_meta.file_path}: {e}") from e

        chunks: list[CodeChunk] = []
        chunks.append(
            CodeChunk(
                repository=file_meta.repository,
                file=file_meta,
                chunk_type=CodeChunk.ChunkType.FILE,
                symbol_name="",
                start_line=1,
                end_line=source.count("\n") + 1,
                content=source,
                metadata={"imports": [], "classes": [], "functions": []},
            )
        )

        ext = (file_meta.extension or "").lower()
        parsed = self.parser.parse_python(source) if ext == "py" else self.parser.parse_other(ext, source)
        chunks[0].metadata = {
            "imports": parsed.imports,
            "classes": [s.name for s in parsed.classes],
            "functions": [s.name for s in parsed.functions],
        }

        lines = source.splitlines()

        def slice_lines(start: int | None, end: int | None) -> str:
            if not start:
                return ""
            s = max(start - 1, 0)
            e = min(end or len(lines), len(lines))
            if e <= s:
                e = min(s + 1, len(lines))
            return "\n".join(lines[s:e])

        for sym in parsed.classes:
            if sym.start_line:
                chunks.append(
                    CodeChunk(
                        repository=file_meta.repository,
                        file=file_meta,
                        chunk_type=CodeChunk.ChunkType.CLASS,
                        symbol_name=sym.name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        content=slice_lines(sym.start_line, sym.end_line),
                        metadata=sym.extra or {},
                    )
                )
        for sym in parsed.functions:
            if sym.start_line:
                chunks.append(
                    CodeChunk(
                        repository=file_meta.repository,
                        file=file_meta,
                        chunk_type=CodeChunk.ChunkType.FUNCTION,
                        symbol_name=sym.name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        content=slice_lines(sym.start_line, sym.end_line),
                        metadata=sym.extra or {},
                    )
                )

        return chunks


class ProcessingPipelineService:
    def __init__(self, chunker: HybridChunkingService | None = None) -> None:
        self.chunker = chunker or HybridChunkingService()

    def run(self, repository: Repository) -> dict:
        if not repository.local_path:
            raise ProcessingError("Repository has no local_path. Run ingestion first.")

        repo_root = Path(repository.local_path)
        if not repo_root.exists():
            raise ProcessingError(f"local_path not found: {repository.local_path}")

        logger.info("Starting processing. repository=%s", repository.id)
        repository.status = Repository.Status.PROCESSING
        repository.save(update_fields=["status", "updated_at"])

        files = list(
            FileMetadata.objects.filter(repository=repository, is_selected=True).order_by("file_path")
        )
        if not files:
            raise ProcessingError("No selected FileMetadata found. Run ingestion first.")

        all_chunks: list[CodeChunk] = []
        for f in files:
            all_chunks.extend(self.chunker.build_chunks(f, repo_root))

        with transaction.atomic():
            CodeChunk.objects.filter(repository=repository).delete()
            CodeChunk.objects.bulk_create(all_chunks, batch_size=250)

        logger.info("Processing complete. repository=%s chunks=%d", repository.id, len(all_chunks))
        repository.status = Repository.Status.COMPLETED
        repository.save(update_fields=["status", "updated_at"])
        return {"repository_id": str(repository.id), "chunk_count": len(all_chunks)}

