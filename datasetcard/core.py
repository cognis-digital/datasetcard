"""Core engine: profile tabular datasets and emit Croissant / cards / datasheets.

No third-party dependencies. Supports CSV/TSV and JSON-lines inputs.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import json
import os
import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_BOOL_VALUES = {"true", "false", "yes", "no", "0", "1", "t", "f"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?")
_NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-"}

# Croissant / schema.org vocabulary types mapped from inferred column types.
_CROISSANT_TYPE = {
    "integer": "sc:Integer",
    "float": "sc:Float",
    "boolean": "sc:Boolean",
    "date": "sc:Date",
    "text": "sc:Text",
}


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    count: int
    missing: int
    unique: int
    samples: list = field(default_factory=list)
    min: Any = None
    max: Any = None
    mean: Any = None
    stdev: Any = None

    @property
    def missing_pct(self) -> float:
        total = self.count + self.missing
        return round(100.0 * self.missing / total, 2) if total else 0.0


@dataclass
class DatasetProfile:
    name: str
    path: str
    file_format: str
    sha256: str
    size_bytes: int
    num_rows: int
    num_columns: int
    columns: list = field(default_factory=list)
    generated_at: str = ""
    pii_flags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["columns"] = [asdict(c) for c in self.columns]
        for col, src in zip(d["columns"], self.columns):
            col["missing_pct"] = src.missing_pct
        return d


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_null(v: str) -> bool:
    return v.strip().lower() in _NULL_TOKENS


def _infer_cell_type(v: str) -> str:
    s = v.strip()
    if _INT_RE.match(s):
        return "integer"
    if _FLOAT_RE.match(s):
        return "float"
    if s.lower() in _BOOL_VALUES and not _INT_RE.match(s):
        return "boolean"
    if _DATE_RE.match(s):
        return "date"
    return "text"


def _reconcile_type(types: set) -> str:
    types = {t for t in types if t}
    if not types:
        return "text"
    if types <= {"integer"}:
        return "integer"
    if types <= {"integer", "float"}:
        return "float"
    if types <= {"boolean"}:
        return "boolean"
    if types <= {"date"}:
        return "date"
    return "text"


# Common PII-bearing column-name signals for governance flagging.
_PII_PATTERNS = {
    "email": re.compile(r"e[-_ ]?mail", re.I),
    "phone": re.compile(r"phone|mobile|tel\b", re.I),
    "ssn": re.compile(r"\bssn\b|social.?security", re.I),
    "name": re.compile(r"\b(first|last|full)?[-_ ]?name\b", re.I),
    "address": re.compile(r"address|street|zip|postal", re.I),
    "dob": re.compile(r"birth|dob\b", re.I),
    "ip": re.compile(r"ip[-_ ]?addr", re.I),
    "credit_card": re.compile(r"card|ccnum|credit", re.I),
}
_EMAIL_VALUE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _detect_pii(col_name: str, samples: list) -> list:
    flags = []
    for label, pat in _PII_PATTERNS.items():
        if pat.search(col_name):
            flags.append(label)
    if any(_EMAIL_VALUE_RE.match(str(s).strip()) for s in samples):
        if "email" not in flags:
            flags.append("email")
    return flags


def _read_rows(path: str) -> tuple:
    """Return (header, rows, file_format). rows is list of list[str]."""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    if ext in (".jsonl", ".ndjson"):
        records = []
        keys = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for k in obj:
                if k not in keys:
                    keys.append(k)
            records.append(obj)
        rows = [["" if r.get(k) is None else str(r.get(k, "")) for k in keys] for r in records]
        return keys, rows, "jsonl"
    delimiter = "\t" if ext == ".tsv" else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows = [r for r in reader]
    if not all_rows:
        return [], [], "csv" if delimiter == "," else "tsv"
    header = all_rows[0]
    rows = all_rows[1:]
    return header, rows, ("csv" if delimiter == "," else "tsv")


def profile_dataset(path: str, name: str = None, max_samples: int = 3) -> DatasetProfile:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"input file not found: {path}")
    header, rows, fmt = _read_rows(path)
    if not header:
        raise ValueError(f"no columns detected in {path}")

    n_cols = len(header)
    col_types: list = [set() for _ in range(n_cols)]
    col_present: list = [[] for _ in range(n_cols)]  # non-null string values
    col_seen: list = [set() for _ in range(n_cols)]
    col_missing = [0] * n_cols

    for row in rows:
        for i in range(n_cols):
            val = row[i] if i < len(row) else ""
            if _is_null(val):
                col_missing[i] += 1
                continue
            col_types[i].add(_infer_cell_type(val))
            col_present[i].append(val)
            if len(col_seen[i]) < 100000:
                col_seen[i].add(val)

    columns: list = []
    pii_flags_all: list = []
    for i, cname in enumerate(header):
        dtype = _reconcile_type(col_types[i])
        present = col_present[i]
        cp = ColumnProfile(
            name=cname,
            dtype=dtype,
            count=len(present),
            missing=col_missing[i],
            unique=len(col_seen[i]),
            samples=present[:max_samples],
        )
        if dtype in ("integer", "float") and present:
            nums = []
            for v in present:
                try:
                    nums.append(float(v))
                except ValueError:
                    pass
            if nums:
                cp.min = min(nums)
                cp.max = max(nums)
                cp.mean = round(statistics.fmean(nums), 6)
                cp.stdev = round(statistics.pstdev(nums), 6) if len(nums) > 1 else 0.0
                if dtype == "integer":
                    cp.min = int(cp.min)
                    cp.max = int(cp.max)
        pii = _detect_pii(cname, present[:50])
        if pii:
            pii_flags_all.append({"column": cname, "types": pii})
        columns.append(cp)

    profile = DatasetProfile(
        name=name or os.path.splitext(os.path.basename(path))[0],
        path=os.path.abspath(path),
        file_format=fmt,
        sha256=sha256_file(path),
        size_bytes=os.path.getsize(path),
        num_rows=len(rows),
        num_columns=n_cols,
        columns=columns,
        generated_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        pii_flags=pii_flags_all,
    )
    return profile


def build_croissant(profile: DatasetProfile) -> dict:
    """Emit a Croissant (ML Commons) JSON-LD metadata record."""
    file_id = f"{profile.name}.{profile.file_format}"
    fields = []
    for col in profile.columns:
        fields.append({
            "@type": "cr:Field",
            "@id": f"{profile.name}/{col.name}",
            "name": col.name,
            "dataType": _CROISSANT_TYPE.get(col.dtype, "sc:Text"),
            "source": {
                "fileObject": {"@id": file_id},
                "extract": {"column": col.name},
            },
        })
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "data": {"@id": "cr:data", "@type": "@json"},
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        },
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": profile.name,
        "description": f"Auto-generated dataset card for {profile.name}.",
        "dateCreated": profile.generated_at,
        "distribution": [{
            "@type": "cr:FileObject",
            "@id": file_id,
            "name": file_id,
            "encodingFormat": {
                "csv": "text/csv",
                "tsv": "text/tab-separated-values",
                "jsonl": "application/jsonlines",
            }.get(profile.file_format, "text/plain"),
            "contentSize": f"{profile.size_bytes} B",
            "sha256": profile.sha256,
        }],
        "recordSet": [{
            "@type": "cr:RecordSet",
            "@id": profile.name,
            "name": profile.name,
            "field": fields,
        }],
    }


def build_card_markdown(profile: DatasetProfile) -> str:
    """Render a HuggingFace-style dataset card with YAML front matter."""
    lines = []
    lines.append("---")
    lines.append(f"dataset_name: {profile.name}")
    lines.append("language: []")
    lines.append("license: unknown")
    lines.append("size_categories:")
    lines.append(f"  - {_size_category(profile.num_rows)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Dataset Card for {profile.name}")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append("")
    lines.append(
        f"Auto-generated card for `{os.path.basename(profile.path)}` "
        f"({profile.file_format.upper()}, {profile.num_rows} rows x {profile.num_columns} columns, "
        f"{profile.size_bytes} bytes)."
    )
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- **Source path:** `{profile.path}`")
    lines.append(f"- **SHA-256:** `{profile.sha256}`")
    lines.append(f"- **Generated at (UTC):** {profile.generated_at}")
    lines.append("")
    lines.append("## Data Fields")
    lines.append("")
    lines.append("| Column | Type | Non-null | Missing % | Unique | Example |")
    lines.append("|--------|------|----------|-----------|--------|---------|")
    for col in profile.columns:
        ex = col.samples[0] if col.samples else ""
        ex = str(ex).replace("|", "\\|")[:40]
        lines.append(
            f"| {col.name} | {col.dtype} | {col.count} | {col.missing_pct} | {col.unique} | {ex} |"
        )
    lines.append("")
    lines.append("## Personal & Sensitive Information")
    lines.append("")
    if profile.pii_flags:
        lines.append("WARNING: potential PII detected. Review before sharing:")
        for f in profile.pii_flags:
            lines.append(f"- `{f['column']}`: {', '.join(f['types'])}")
    else:
        lines.append("No obvious PII signals detected in column names or sampled values.")
    lines.append("")
    return "\n".join(lines)


def _size_category(n: int) -> str:
    bounds = [
        (1000, "n<1K"), (10000, "1K<n<10K"), (100000, "10K<n<100K"),
        (1000000, "100K<n<1M"), (10000000, "1M<n<10M"),
    ]
    for limit, label in bounds:
        if n < limit:
            return label
    return "n>10M"


_DATASHEET_QUESTIONS = [
    ("Motivation", "For what purpose was the dataset created?"),
    ("Composition", "What do the instances represent and how many are there?"),
    ("Collection", "How was the data associated with each instance acquired?"),
    ("Preprocessing", "Was any preprocessing/cleaning/labeling done?"),
    ("Uses", "Has the dataset been used for any tasks already?"),
    ("Distribution", "How will the dataset be distributed?"),
    ("Maintenance", "Who will maintain the dataset and how?"),
]


def build_datasheet(profile: DatasetProfile) -> dict:
    """Gebru et al. 'Datasheets for Datasets' skeleton, pre-filled where known."""
    composition = (
        f"The dataset contains {profile.num_rows} instances across "
        f"{profile.num_columns} fields: "
        + ", ".join(f"{c.name} ({c.dtype})" for c in profile.columns) + "."
    )
    answers = {}
    for section, question in _DATASHEET_QUESTIONS:
        answers[section] = {"question": question, "answer": "TODO: fill in."}
    answers["Composition"]["answer"] = composition
    answers["Distribution"]["answer"] = (
        f"File format {profile.file_format.upper()}, {profile.size_bytes} bytes, "
        f"SHA-256 {profile.sha256}."
    )
    return {
        "dataset": profile.name,
        "generated_at": profile.generated_at,
        "pii_flags": profile.pii_flags,
        "sections": answers,
    }
