from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


LANES = (
    "unknown_real_word_candidates",
    "math_terms_or_symbols",
    "math_markup",
    "domain_notation_anchors",
    "structural_source_anchors",
    "source_id_artifacts",
    "source_cleanup_candidates",
    "null_symbol_anchors",
)

MATH_MARKUP = {
    "annotation",
    "columnalign",
    "mathvariant",
    "mathsize",
    "menclose",
    "mfenced",
    "mfrac",
    "mi",
    "mn",
    "mo",
    "mover",
    "mroot",
    "mrow",
    "mspace",
    "msqrt",
    "mstyle",
    "msub",
    "msubsup",
    "msup",
    "mtable",
    "mtd",
    "mtext",
    "mtr",
    "munder",
    "munderover",
    "rowalign",
    "semantics",
    "stretchy",
}

MATH_TERMS = {
    "absolute",
    "arccosine",
    "arcsine",
    "arctangent",
    "asymptote",
    "binomial",
    "coefficient",
    "cosine",
    "cotangent",
    "cosecant",
    "derivative",
    "determinant",
    "divisor",
    "ellipse",
    "exponent",
    "exponential",
    "factorial",
    "fraction",
    "function",
    "hyperbola",
    "integral",
    "intercept",
    "logarithm",
    "matrix",
    "multiplication",
    "numerator",
    "parabola",
    "polynomial",
    "quadratic",
    "radical",
    "secant",
    "sine",
    "subscript",
    "summation",
    "superscript",
    "tangent",
    "trinomial",
    "variable",
    "vector",
}

MATH_SYMBOLS = {
    "+": "plus",
    "-": "minus",
    "−": "minus",
    "–": "minus",
    "×": "multiplication",
    "÷": "division",
    "·": "dot",
    "⋅": "dot product",
    "∙": "dot operator",
    "=": "equals",
    "≠": "not equals",
    "≈": "approximately equals",
    "≡": "identical to",
    "≟": "questioned equals",
    "≤": "less than or equal",
    "≥": "greater than or equal",
    "∞": "infinity",
    "π": "pi",
    "θ": "theta",
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "λ": "lambda",
    "μ": "mu",
    "µ": "micro",
    "ν": "nu",
    "ρ": "rho",
    "σ": "sigma",
    "ω": "omega",
    "ψ": "psi",
    "χ": "chi",
    "Σ": "summation",
    "Δ": "delta",
    "∆": "delta",
    "∫": "integral",
    "∑": "summation",
    "∪": "union",
    "∩": "intersection",
    "√": "square root",
    "∘": "composition",
    "∠": "angle",
    "ℓ": "script l",
    "ℳ": "script m",
    "∼": "similar to",
    "′": "prime",
    "¯": "overbar",
    "°": "degree",
    "±": "plus or minus",
    "→": "right arrow",
    "⟶": "right arrow",
    "⇌": "equilibrium arrows",
    "〈": "left angle bracket",
    "〉": "right angle bracket",
}

STRUCTURAL_SOURCE_ANCHORS = {
    "alt",
    "class",
    "cnxml",
    "colname",
    "colnum",
    "colsep",
    "colspec",
    "data",
    "display",
    "document",
    "eip",
    "entry",
    "fs",
    "gif",
    "href",
    "id",
    "idm",
    "jpeg",
    "jpg",
    "mdml",
    "nameend",
    "namest",
    "newline",
    "ost",
    "pdf",
    "png",
    "resource",
    "rowsep",
    "src",
    "svg",
    "target",
    "tbody",
    "tgroup",
    "thead",
    "tbl",
    "tif",
    "tiff",
    "type",
    "valign",
    "webp",
    "xmlns",
    "ⓐ",
    "ⓑ",
    "ⓒ",
    "ⓓ",
    "ⓔ",
    "ⓕ",
}

SOURCE_CLEANUP_CANDIDATES = {
    "columnalign": "column align",
    "mathsize": "math size",
    "mathvariant": "math variant",
    "rowalign": "row align",
}

ABBREVIATION_EXPANSIONS = {
    "aques03s": "self check questions 03 solution",
    "ctques": "critical thinking questions",
    "rques": "review questions",
    "sques": "self check questions",
}

DOMAIN_NOTATION_EXPANSIONS = {
    "csc": "cosecant",
    "gcf": "greatest common factor",
    "hcl": "hydrochloric acid",
    "ln": "natural logarithm",
    "sec": "secant",
    "sqrt": "square root",
}

MOJIBAKE_PREFIXES = ("â", "Ã", "Â", "Î", "Ï", "ð")
SOURCE_ID_PATTERN = re.compile(
    r"(?:^|[_-])(?:ch\d+|mod\d+|fig(?:ure)?|table|review_questions|self_check_questions|critical_thinking_questions|problem|solution)(?:$|[_-])",
    re.IGNORECASE,
)
WORDLIKE_PATTERN = re.compile(r"^[a-z][a-z'-]{2,}$")
SIMPLE_SURFACE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def classify_unknown_anchor(anchor: str, context: str | None = None) -> dict[str, Any]:
    surface = str(anchor or "").strip()
    lowered = surface.casefold()
    context_text = str(context or "")

    if not surface:
        return _classification(surface, "null_symbol_anchors", "empty anchor maps to NULL")

    if _looks_like_embedded_markup(surface):
        return _classification(surface, "null_symbol_anchors", "embedded markup fragment maps to NULL")

    if _looks_like_source_id(surface):
        return _classification(surface, "source_id_artifacts", "source id or generated locator")

    if lowered in SOURCE_CLEANUP_CANDIDATES and not _prose_context(context_text):
        return _classification(
            surface,
            "source_cleanup_candidates",
            "conjoined source attribute with readable expansion",
            expansion=SOURCE_CLEANUP_CANDIDATES[lowered],
        )

    if lowered in ABBREVIATION_EXPANSIONS:
        return _classification(
            surface,
            "source_cleanup_candidates",
            "abbreviation with readable expansion",
            expansion=ABBREVIATION_EXPANSIONS[lowered],
        )

    if lowered in DOMAIN_NOTATION_EXPANSIONS:
        return _classification(
            surface,
            "domain_notation_anchors",
            "domain notation with readable expansion",
            expansion=DOMAIN_NOTATION_EXPANSIONS[lowered],
        )

    if lowered in MATH_MARKUP:
        lane = "unknown_real_word_candidates" if _prose_context(context_text) else "math_markup"
        reason = "prose word surface" if lane == "unknown_real_word_candidates" else "MathML tag or attribute"
        return _classification(surface, lane, reason)

    if surface in MATH_SYMBOLS:
        return _classification(surface, "math_terms_or_symbols", "math symbol", expansion=MATH_SYMBOLS[surface])

    if lowered in MATH_TERMS:
        return _classification(surface, "math_terms_or_symbols", "math vocabulary")

    if lowered in STRUCTURAL_SOURCE_ANCHORS:
        return _classification(surface, "structural_source_anchors", "source markup anchor")

    if any(surface.startswith(prefix) for prefix in MOJIBAKE_PREFIXES):
        return _classification(surface, "null_symbol_anchors", "mojibake artifact maps to NULL")

    if _is_word_surface(surface):
        return _classification(surface, "unknown_real_word_candidates", "word-like surface")

    if not SIMPLE_SURFACE_PATTERN.fullmatch(surface):
        return _classification(surface, "null_symbol_anchors", "non-anchor markup or symbol fragment maps to NULL")

    if WORDLIKE_PATTERN.fullmatch(lowered):
        return _classification(surface, "unknown_real_word_candidates", "word-like surface")

    return _classification(surface, "null_symbol_anchors", "unclassified short or code-like anchor maps to NULL")


def classify_unknown_anchor_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    lane_rows: dict[str, list[dict[str, Any]]] = {lane: [] for lane in LANES}
    lane_observations: dict[str, int] = {lane: 0 for lane in LANES}
    total_unique = 0
    total_observations = 0

    for row in rows:
        anchor = str(row.get("anchor") or "")
        observations = int(row.get("observations", 0) or 0)
        context = row.get("context") or row.get("proof_context") or row.get("source_context") or ""
        classified = classify_unknown_anchor(anchor, str(context))
        lane = classified["lane"]
        payload = dict(row)
        payload.update(classified)
        lane_rows[lane].append(payload)
        lane_observations[lane] += observations
        total_unique += 1
        total_observations += observations

    for lane in LANES:
        lane_rows[lane].sort(key=lambda item: (-int(item.get("observations", 0) or 0), str(item.get("anchor", ""))))

    return {
        "ok": True,
        "schema_version": "anchorworks_unknown_anchor_classification@1",
        "total_unique": total_unique,
        "total_observations": total_observations,
        "lane_counts": {lane: len(lane_rows[lane]) for lane in LANES},
        "lane_observations": lane_observations,
        "lanes": lane_rows,
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def write_classified_unknown_report(rows: Iterable[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    classified = classify_unknown_anchor_rows(rows)

    lane_paths: dict[str, str] = {}
    for lane in LANES:
        path = output_dir / f"{lane}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in classified["lanes"][lane]:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        lane_paths[lane] = str(path)

    summary = {
        key: value
        for key, value in classified.items()
        if key != "lanes"
    }
    summary["lane_paths"] = lane_paths
    summary_path = output_dir / "classified_unknown_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    result = dict(summary)
    result["summary_path"] = str(summary_path)
    return result


def write_math_lexicon(path: Path) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "anchorworks_math_lexicon@1",
        "terms": sorted(MATH_TERMS),
        "symbols": dict(sorted(MATH_SYMBOLS.items(), key=lambda item: item[1])),
        "markup": sorted(MATH_MARKUP),
        "role": "reference_lane_not_canonical_word_memory",
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "ok": True,
        "path": str(path),
        "term_count": len(payload["terms"]),
        "symbol_count": len(payload["symbols"]),
        "markup_count": len(payload["markup"]),
        "writes_allowed": payload["writes_allowed"],
    }


def _classification(anchor: str, lane: str, reason: str, *, expansion: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "anchor": anchor,
        "lane": lane,
        "classification_reason": reason,
    }
    if expansion:
        payload["expansion"] = expansion
    return payload


def _looks_like_embedded_markup(surface: str) -> bool:
    return any(part in surface for part in ("<", ">", "/>", "=\"", "</", "m:"))


def _looks_like_source_id(surface: str) -> bool:
    lowered = surface.casefold()
    if SOURCE_ID_PATTERN.search(lowered):
        return True
    return bool(re.search(r"^(?:[a-z]+)?\d+[a-z]*(?:[_-][a-z0-9]+)+$", lowered))


def _prose_context(context: str) -> bool:
    if not context:
        return False
    lowered = context.casefold()
    return "<" not in lowered and ">" not in lowered and "m:" not in lowered and "mathml" not in lowered


def _is_word_surface(surface: str) -> bool:
    value = str(surface or "").strip()
    if len(value) < 3:
        return False
    has_letter = False
    for index, char in enumerate(value):
        if char.isalpha():
            has_letter = True
            continue
        if char in {"'", "\u2019", "\u2018"} and 0 < index < len(value) - 1:
            continue
        return False
    return has_letter
