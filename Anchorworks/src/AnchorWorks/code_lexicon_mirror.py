from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from .intake import compose_anchor_stream


CODE_LEXICON_MIRROR_SCHEMA_VERSION = "anchorworks_code_lexicon_mirror@1"
CODE_LEXICON_MIRROR_RECEIPT_SCHEMA_VERSION = "anchorworks_code_lexicon_mirror_receipt@1"

WRITE_POLICY = {
    "canonical": False,
    "structural": False,
    "lexicon": False,
    "counts": False,
    "lifetime": False,
}

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    "outputs",
    "generated_media",
}

PYTHON_SUFFIX = ".py"
RUST_SUFFIX = ".rs"

PYTHON_IDENTIFIER_KINDS = {
    "class",
    "function",
    "argument",
    "variable",
    "attribute",
    "import",
}

RUST_KEYWORDS = {
    "as",
    "async",
    "await",
    "break",
    "const",
    "continue",
    "crate",
    "dyn",
    "else",
    "enum",
    "extern",
    "false",
    "fn",
    "for",
    "if",
    "impl",
    "in",
    "let",
    "loop",
    "match",
    "mod",
    "move",
    "mut",
    "pub",
    "ref",
    "return",
    "self",
    "Self",
    "static",
    "struct",
    "super",
    "trait",
    "true",
    "type",
    "unsafe",
    "use",
    "where",
    "while",
}


@dataclass(frozen=True)
class CodeIdentifier:
    source_repo: str
    repo_root: Path
    file_path: Path
    language: str
    identifier: str
    identifier_kind: str
    line: int


def identifier_anchor_stream(identifier: str) -> list[str]:
    """Convert a code identifier into AnchorWorks-style anchor pieces."""
    parts = _split_identifier_parts(identifier)
    stream: list[str] = []
    for part in parts:
        stream.extend(compose_anchor_stream(part))
    return stream


def build_code_lexicon_mirror(
    repo_roots: dict[str, str | Path],
    *,
    excluded_dirs: set[str] | None = None,
) -> dict[str, Any]:
    clean_roots = {
        str(name): Path(root).expanduser().resolve()
        for name, root in sorted(repo_roots.items(), key=lambda item: item[0])
    }
    identifiers: list[CodeIdentifier] = []
    for source_repo, root in clean_roots.items():
        identifiers.extend(_scan_repo(source_repo=source_repo, root=root, excluded_dirs=excluded_dirs))

    entries = [_entry_from_identifier(row) for row in sorted(identifiers, key=_identifier_sort_key)]
    language_counts: dict[str, int] = {}
    repo_counts: dict[str, int] = {}
    unique_identifiers: set[str] = set()
    for entry in entries:
        language_counts[entry["language"]] = language_counts.get(entry["language"], 0) + 1
        repo_counts[entry["source_repo"]] = repo_counts.get(entry["source_repo"], 0) + 1
        unique_identifiers.add(entry["normalized_identifier"])

    payload = {
        "schema_version": CODE_LEXICON_MIRROR_SCHEMA_VERSION,
        "kind": "code_lexicon_mirror",
        "created_at_utc": _utc_now(),
        "source_repo_count": len(clean_roots),
        "source_repos": [
            {"source_repo": name, "repo_id": index, "root": str(root)}
            for index, (name, root) in enumerate(clean_roots.items())
        ],
        "entry_contract": {
            "source_repo": "repo key from source_repos",
            "relative_path": "path inside that repo",
            "language": "python|rust",
            "identifier": "code identifier surface",
            "anchor_stream": "AnchorWorks anchor decomposition",
        },
        "languages": sorted(language_counts),
        "language_counts": language_counts,
        "repo_counts": repo_counts,
        "entry_count": len(entries),
        "unique_identifier_count": len(unique_identifiers),
        "mirror_only": True,
        "live_lexicon_entry": False,
        "authority": "repo_code_mirror",
        "writes_allowed": dict(WRITE_POLICY),
        "promotion_required": True,
        "entries": entries,
    }
    payload["mirror_sha256"] = _hash_payload({key: value for key, value in payload.items() if key != "mirror_sha256"})
    return payload


def write_code_lexicon_mirror(
    repo_roots: dict[str, str | Path],
    *,
    output_root: str | Path,
    excluded_dirs: set[str] | None = None,
) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    mirror_dir = root / "code_lexicon_mirror"
    receipt_dir = mirror_dir / "receipts"
    mirror_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    mirror = build_code_lexicon_mirror(repo_roots, excluded_dirs=excluded_dirs)
    mirror_path = mirror_dir / "code_lexicon_mirror.json"
    mirror_path.write_text(json.dumps(mirror, ensure_ascii=False, indent=2), encoding="utf-8")

    receipt = {
        "schema_version": CODE_LEXICON_MIRROR_RECEIPT_SCHEMA_VERSION,
        "created_at_utc": _utc_now(),
        "mirror_path": str(mirror_path),
        "mirror_sha256": mirror["mirror_sha256"],
        "entry_count": mirror["entry_count"],
        "source_repo_count": mirror["source_repo_count"],
        "writes_performed": ["mirror", "receipt"],
        "forbidden_writes": ["canonical", "structural", "lexicon", "counts", "lifetime"],
        "mirror_only": True,
        "promotion_required": True,
    }
    receipt["receipt_sha256"] = _hash_payload(receipt)
    receipt_path = receipt_dir / f"code_lexicon_mirror_receipt_{_file_timestamp()}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "mirror_path": str(mirror_path),
        "receipt_path": str(receipt_path),
        "mirror_sha256": mirror["mirror_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "entry_count": mirror["entry_count"],
    }


def _scan_repo(
    *,
    source_repo: str,
    root: Path,
    excluded_dirs: set[str] | None,
) -> list[CodeIdentifier]:
    if not root.exists():
        return []
    excludes = set(DEFAULT_EXCLUDED_DIRS)
    if excluded_dirs:
        excludes.update(excluded_dirs)
    rows: list[CodeIdentifier] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in excludes for part in path.parts):
            continue
        if path.suffix == PYTHON_SUFFIX:
            rows.extend(_extract_python_identifiers(source_repo=source_repo, root=root, path=path))
        elif path.suffix == RUST_SUFFIX:
            rows.extend(_extract_rust_identifiers(source_repo=source_repo, root=root, path=path))
    return rows


def _extract_python_identifiers(*, source_repo: str, root: Path, path: Path) -> list[CodeIdentifier]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return []
    rows: list[CodeIdentifier] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            rows.append(_identifier(source_repo, root, path, "python", node.name, "class", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append(_identifier(source_repo, root, path, "python", node.name, "function", node.lineno))
            rows.extend(_python_arguments(source_repo=source_repo, root=root, path=path, node=node))
        elif isinstance(node, ast.Name):
            rows.append(_identifier(source_repo, root, path, "python", node.id, "variable", getattr(node, "lineno", 0)))
        elif isinstance(node, ast.Attribute):
            rows.append(_identifier(source_repo, root, path, "python", node.attr, "attribute", getattr(node, "lineno", 0)))
        elif isinstance(node, ast.alias):
            name = node.asname or node.name.rsplit(".", 1)[-1]
            rows.append(_identifier(source_repo, root, path, "python", name, "import", 0))
    return _dedupe_identifiers(row for row in rows if row.identifier_kind in PYTHON_IDENTIFIER_KINDS)


def _python_arguments(
    *,
    source_repo: str,
    root: Path,
    path: Path,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[CodeIdentifier]:
    args = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    if node.args.vararg:
        args.append(node.args.vararg)
    if node.args.kwarg:
        args.append(node.args.kwarg)
    return [_identifier(source_repo, root, path, "python", arg.arg, "argument", arg.lineno) for arg in args]


def _extract_rust_identifiers(*, source_repo: str, root: Path, path: Path) -> list[CodeIdentifier]:
    text = _strip_rust_comments_and_strings(path.read_text(encoding="utf-8", errors="ignore"))
    rows: list[CodeIdentifier] = []
    line_starts = _line_starts(text)
    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text):
        identifier = match.group(0)
        if identifier in RUST_KEYWORDS or identifier.startswith("_"):
            continue
        kind = _rust_identifier_kind(text, match.start())
        rows.append(_identifier(source_repo, root, path, "rust", identifier, kind, _line_for_index(line_starts, match.start())))
    return _dedupe_identifiers(rows)


def _rust_identifier_kind(text: str, start: int) -> str:
    before = text[max(0, start - 40):start]
    if re.search(r"\bfn\s+$", before):
        return "function"
    if re.search(r"\bstruct\s+$", before):
        return "struct"
    if re.search(r"\benum\s+$", before):
        return "enum"
    if re.search(r"\btrait\s+$", before):
        return "trait"
    if re.search(r"\blet\s+(?:mut\s+)?$", before):
        return "variable"
    if re.search(r"[:,]\s*$", before):
        return "field_or_argument"
    return "identifier"


def _entry_from_identifier(row: CodeIdentifier) -> dict[str, Any]:
    anchor_stream = identifier_anchor_stream(row.identifier)
    normalized_identifier = row.identifier.casefold()
    return {
        "source_repo": row.source_repo,
        "relative_path": str(row.file_path.relative_to(row.repo_root)),
        "language": row.language,
        "identifier": row.identifier,
        "normalized_identifier": normalized_identifier,
        "identifier_kind": row.identifier_kind,
        "line": row.line,
        "anchor_stream": anchor_stream,
        "anchor_count": len(anchor_stream),
        "identifier_sha256": sha256(f"{row.source_repo}|{row.file_path}|{row.identifier}|{row.line}".encode("utf-8")).hexdigest(),
        "mirror_only": True,
        "live_lexicon_entry": False,
        "promotion_required": True,
    }


def _identifier(
    source_repo: str,
    root: Path,
    path: Path,
    language: str,
    identifier: str,
    kind: str,
    line: int,
) -> CodeIdentifier:
    return CodeIdentifier(
        source_repo=source_repo,
        repo_root=root,
        file_path=path,
        language=language,
        identifier=str(identifier),
        identifier_kind=kind,
        line=int(line or 0),
    )


def _dedupe_identifiers(rows: Iterable[CodeIdentifier]) -> list[CodeIdentifier]:
    seen: set[tuple[str, str, str, str, int]] = set()
    out: list[CodeIdentifier] = []
    for row in rows:
        if not _is_identifier_surface(row.identifier):
            continue
        key = (str(row.file_path), row.language, row.identifier, row.identifier_kind, row.line)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _split_identifier_parts(identifier: str) -> list[str]:
    pieces = re.split(r"[^A-Za-z0-9]+", str(identifier or ""))
    out: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        out.extend(_split_camel_and_digits(piece))
    return out


def _split_camel_and_digits(value: str) -> list[str]:
    pattern = re.compile(
        r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+|[A-Z]+"
    )
    return [match.group(0) for match in pattern.finditer(value)]


def _is_identifier_surface(identifier: str) -> bool:
    value = str(identifier or "")
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value))


def _strip_rust_comments_and_strings(text: str) -> str:
    text = re.sub(r"//.*", " ", text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'r#*".*?"#*', '""', text, flags=re.S)
    text = re.sub(r'".*?"', '""', text, flags=re.S)
    text = re.sub(r"'.'", "''", text)
    return text


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _line_for_index(starts: list[int], index: int) -> int:
    line = 1
    for start in starts:
        if start > index:
            break
        line += 1
    return max(1, line - 1)


def _identifier_sort_key(row: CodeIdentifier) -> tuple[str, str, str, int, str]:
    return (row.source_repo, str(row.file_path), row.identifier_kind, row.line, row.identifier)


def _hash_payload(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
