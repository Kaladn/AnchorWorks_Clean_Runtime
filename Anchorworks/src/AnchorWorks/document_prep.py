from __future__ import annotations

import csv
import hashlib
import html.parser
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .chat_bridge import bridge_chat_memory_json


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".log",
    ".text",
    ".csv.txt",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".scss",
    ".jsonl",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".toml",
}
DELIMITED_EXTENSIONS = {".csv", ".tsv", ".psv"}
JSON_EXTENSIONS = {".json", ".jsonld", ".geojson"}
XML_EXTENSIONS = {".xml", ".xhtml", ".opf", ".svg"}
HTML_EXTENSIONS = {".html", ".htm"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xlsm"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
RTF_EXTENSIONS = {".rtf"}
ODT_EXTENSIONS = {".odt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
VISUAL_LEADER_RE = re.compile(r"[\u2500-\u257F]+")


@dataclass
class PreparedDocument:
    source_name: str
    source_path: str
    file_type: str
    original_size: int
    sha256: str
    converter: str
    prepared_text: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_file(source_path: Path) -> PreparedDocument:
    path = Path(source_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        raise IsADirectoryError(path)
    return prepare_bytes(
        path.read_bytes(),
        source_name=path.name,
        source_path=str(path),
        file_type=_guess_file_type(path.name),
    )


def prepare_bytes(
    raw: bytes,
    *,
    source_name: str,
    source_path: str = "",
    file_type: str = "",
) -> PreparedDocument:
    source_name = Path(source_name or "document").name
    suffix = Path(source_name).suffix.lower()
    file_type = file_type or _guess_file_type(source_name)
    warnings: list[str] = []
    metadata: dict[str, Any] = {}

    try:
        if suffix in DELIMITED_EXTENSIONS:
            text, metadata = _prepare_delimited(raw, source_name, suffix)
            converter = "delimited-table"
        elif suffix in JSON_EXTENSIONS:
            text, metadata = _prepare_json(raw, source_name)
            converter = str(metadata.pop("_converter", "json-structure"))
        elif suffix in HTML_EXTENSIONS:
            text, metadata = _prepare_html(raw, source_name)
            converter = "html-text"
        elif suffix in XML_EXTENSIONS:
            text, metadata = _prepare_xml(raw, source_name)
            converter = "xml-structure"
        elif suffix in PDF_EXTENSIONS:
            text, metadata = _prepare_pdf(raw, source_name)
            converter = "pdf-text"
        elif suffix in DOCX_EXTENSIONS:
            text, metadata = _prepare_docx(raw, source_name)
            converter = "docx-text"
        elif suffix in SPREADSHEET_EXTENSIONS:
            text, metadata = _prepare_spreadsheet(raw, source_name)
            converter = "spreadsheet-table"
        elif suffix in RTF_EXTENSIONS:
            text, metadata = _prepare_rtf(raw, source_name)
            converter = "rtf-text"
        elif suffix in ODT_EXTENSIONS:
            text, metadata = _prepare_odt(raw, source_name)
            converter = "odt-text"
        elif suffix in IMAGE_EXTENSIONS:
            text, metadata = _prepare_image(raw, source_name)
            converter = "image-metadata"
        else:
            text = _decode_text(raw)
            metadata = {"text_characters": len(text)}
            converter = "plain-text"
    except Exception as exc:
        try:
            text = _decode_text(raw)
            converter = "plain-text-fallback"
            warnings.append(f"{suffix or 'unknown'} converter failed: {exc}")
            metadata = {"text_characters": len(text)}
        except Exception:
            text = _prepare_binary_fallback(raw, source_name)
            converter = "binary-metadata-fallback"
            warnings.append(f"{suffix or 'unknown'} converter failed: {exc}")
            metadata = {"binary_fallback": True}

    text, stripped_leader_count = _strip_visual_leaders(text)
    if stripped_leader_count:
        metadata["stripped_visual_leader_characters"] = stripped_leader_count

    return PreparedDocument(
        source_name=source_name,
        source_path=source_path,
        file_type=file_type,
        original_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        converter=converter,
        prepared_text=text,
        warnings=warnings,
        metadata=metadata,
    )


def _decode_text(raw: bytes) -> str:
    for encoding in ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1252"]:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unable to decode file as text")


def _strip_visual_leaders(text: str) -> tuple[str, int]:
    matches = list(VISUAL_LEADER_RE.finditer(text))
    if not matches:
        return text, 0
    stripped_count = sum(match.end() - match.start() for match in matches)
    return VISUAL_LEADER_RE.sub(" ", text), stripped_count


def _prepare_delimited(raw: bytes, source_name: str, suffix: str) -> tuple[str, dict[str, Any]]:
    text = _decode_text(raw)
    delimiter = "\t" if suffix == ".tsv" else "|" if suffix == ".psv" else ","
    if suffix == ".csv":
        try:
            dialect = csv.Sniffer().sniff(text[:8192])
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    lines = [_source_line(source_name), "[TYPE: table]", "", f"[TABLE: {Path(source_name).stem}]"]
    lines.extend(" | ".join(_clean_cell(cell) for cell in row) for row in rows)
    lines.append("[TABLE_END]")
    return "\n".join(lines), {"rows": len(rows), "delimiter": delimiter}


def _prepare_json(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    data = json.loads(_decode_text(raw))
    bridged = bridge_chat_memory_json(data, source_name)
    if bridged is not None:
        metadata = dict(bridged.metadata)
        metadata["_converter"] = "chat-memory-bridge"
        return bridged.text, metadata

    rows: list[str] = []
    _flatten_json(data, "root", rows)
    lines = [_source_line(source_name), "[TYPE: json]", "", f"[JSON: {Path(source_name).stem}]"]
    lines.extend(rows or ["root | null |"])
    lines.append("[JSON_END]")
    return "\n".join(lines), {"rows": len(rows)}


def _flatten_json(value: Any, path: str, rows: list[str]) -> None:
    if isinstance(value, dict):
        if not value:
            rows.append(f"{path} | object | empty")
        for key, child in value.items():
            safe_key = str(key).replace("\n", " ").strip()
            _flatten_json(child, f"{path}.{safe_key}", rows)
    elif isinstance(value, list):
        if not value:
            rows.append(f"{path} | array | empty")
        for index, child in enumerate(value):
            _flatten_json(child, f"{path}.{index}", rows)
    else:
        rows.append(f"{path} | {type(value).__name__} | {_clean_cell(value)}")


def _prepare_xml(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    root = ElementTree.fromstring(raw)
    rows: list[str] = []
    _walk_xml(root, rows, depth=0)
    lines = [_source_line(source_name), "[TYPE: xml]", "", f"[XML: {Path(source_name).stem}]"]
    lines.extend(rows)
    lines.append("[XML_END]")
    return "\n".join(lines), {"rows": len(rows), "root": _strip_namespace(root.tag)}


def _walk_xml(element: ElementTree.Element, rows: list[str], depth: int) -> None:
    tag = _strip_namespace(element.tag)
    rows.append(f"[ELEMENT: {tag}]")
    for key, value in element.attrib.items():
        rows.append(f"[ATTR: {_strip_namespace(key)}] {_clean_cell(value)}")
    text = (element.text or "").strip()
    if text:
        rows.append(f"[TEXT] {_clean_cell(text)}")
    for child in list(element):
        _walk_xml(child, rows, depth + 1)
        tail = (child.tail or "").strip()
        if tail:
            rows.append(f"[TEXT] {_clean_cell(tail)}")
    rows.append(f"[ELEMENT_END: {tag}]")


def _prepare_html(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    parser = _HTMLTextExtractor()
    parser.feed(_decode_text(raw))
    parser.close()
    lines = [_source_line(source_name), "[TYPE: html]", "", f"[HTML: {Path(source_name).stem}]"]
    lines.extend(parser.lines)
    lines.append("[HTML_END]")
    return "\n".join(lines), {"lines": len(parser.lines)}


def _prepare_pdf(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        raise ValueError("PDF conversion needs pypdf installed") from exc

    reader = PdfReader(io.BytesIO(raw))
    lines = [_source_line(source_name), "[TYPE: pdf]", "", f"[PDF: {Path(source_name).stem}]"]
    for page_index, page in enumerate(reader.pages, start=1):
        lines.append("")
        lines.append(f"[PAGE: {page_index}]")
        lines.append(page.extract_text() or "")
    lines.append("[PDF_END]")
    return "\n".join(lines), {"pages": len(reader.pages)}


def _prepare_docx(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        raise ValueError("DOCX conversion needs python-docx installed") from exc

    doc = Document(io.BytesIO(raw))
    lines = [_source_line(source_name), "[TYPE: docx]", "", f"[DOCX: {Path(source_name).stem}]"]
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)
    for table_index, table in enumerate(doc.tables, start=1):
        lines.extend(["", f"[TABLE: {Path(source_name).stem} {table_index}]"])
        for row in table.rows:
            lines.append(" | ".join(_clean_cell(cell.text) for cell in row.cells))
        lines.append("[TABLE_END]")
    lines.append("[DOCX_END]")
    return "\n".join(lines), {"paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}


def _prepare_spreadsheet(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        raise ValueError("spreadsheet conversion needs openpyxl installed") from exc

    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    lines = [_source_line(source_name), "[TYPE: spreadsheet]", "", f"[SPREADSHEET: {Path(source_name).stem}]"]
    row_count = 0
    for sheet in workbook.worksheets:
        lines.extend(["", f"[TABLE: {sheet.title}]"])
        for row in sheet.iter_rows(values_only=True):
            values = [_clean_cell(value) for value in row]
            if any(values):
                row_count += 1
                lines.append(" | ".join(values))
        lines.append("[TABLE_END]")
    lines.append("[SPREADSHEET_END]")
    return "\n".join(lines), {"sheets": len(workbook.worksheets), "rows": row_count}


def _prepare_rtf(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    text = _decode_text(raw)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ").replace("\\", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [_source_line(source_name), "[TYPE: rtf]", "", f"[RTF: {Path(source_name).stem}]", text.strip(), "[RTF_END]"]
    return "\n".join(lines), {"text_characters": len(text)}


def _prepare_odt(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        content = archive.read("content.xml")
    root = ElementTree.fromstring(content)
    rows: list[str] = []
    for element in root.iter():
        text = "".join(element.itertext()).strip()
        if text:
            rows.append(_clean_cell(text))
    lines = [_source_line(source_name), "[TYPE: odt]", "", f"[ODT: {Path(source_name).stem}]"]
    lines.extend(dict.fromkeys(rows))
    lines.append("[ODT_END]")
    return "\n".join(lines), {"lines": len(rows)}


def _prepare_image(raw: bytes, source_name: str) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    warnings: list[str] = []
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as image:
            metadata = {
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
            }
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        warnings.append(str(exc))

    lines = [
        _source_line(source_name),
        "[TYPE: image]",
        "",
        f"[IMAGE: {Path(source_name).stem}]",
        f"Format: {metadata.get('format', Path(source_name).suffix.lower().lstrip('.'))}",
        f"Width: {metadata.get('width', 'unknown')}",
        f"Height: {metadata.get('height', 'unknown')}",
        f"Mode: {metadata.get('mode', 'unknown')}",
        f"SHA256: {hashlib.sha256(raw).hexdigest()}",
        "[IMAGE_END]",
    ]
    if warnings:
        metadata["warnings"] = warnings
    return "\n".join(lines), metadata


def _prepare_binary_fallback(raw: bytes, source_name: str) -> str:
    sample = raw[:2048].hex(" ")
    return "\n".join(
        [
            _source_line(source_name),
            "[TYPE: binary]",
            "",
            f"[BINARY_FILE: {Path(source_name).stem}]",
            f"Extension: {Path(source_name).suffix.lower() or 'none'}",
            f"Size_Bytes: {len(raw)}",
            f"SHA256: {hashlib.sha256(raw).hexdigest()}",
            "[BYTE_HEX_SAMPLE_START]",
            sample,
            "[BYTE_HEX_SAMPLE_END]",
        ]
    )


class _HTMLTextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._current: list[str] = []
        self._skip_depth = 0
        self._cell_row: list[str] | None = None
        self._cell_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "tr":
            self._flush_line()
            self._cell_row = []
        elif tag in {"td", "th"}:
            self._cell_text = []
        elif tag in {"br", "p", "div", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in {"td", "th"} and self._cell_row is not None:
            self._cell_row.append(_clean_cell(" ".join(self._cell_text or [])))
            self._cell_text = None
        elif tag == "tr" and self._cell_row is not None:
            if any(self._cell_row):
                self.lines.append(" | ".join(self._cell_row))
            self._cell_row = None
        elif tag in {"p", "div", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self._flush_line()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._cell_text is not None:
            self._cell_text.append(text)
        else:
            self._current.append(text)

    def close(self) -> None:
        self._flush_line()
        super().close()

    def _flush_line(self) -> None:
        if self._current:
            line = _clean_cell(" ".join(self._current))
            if line:
                self.lines.append(line)
            self._current = []


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _source_line(source_name: str) -> str:
    return f"[SOURCE: {source_name}]"


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _guess_file_type(source_name: str) -> str:
    suffix = Path(source_name).suffix.lower().lstrip(".")
    return suffix or "unknown"
