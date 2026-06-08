"""Command-line interface for datasetcard."""
from __future__ import annotations

import argparse
import json
import sys

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    profile_dataset,
    build_croissant,
    build_card_markdown,
    build_datasheet,
)


def _print_profile_table(profile) -> None:
    print(f"Dataset: {profile.name}")
    print(f"Format : {profile.file_format}")
    print(f"Rows   : {profile.num_rows}")
    print(f"Columns: {profile.num_columns}")
    print(f"SHA-256: {profile.sha256}")
    if profile.pii_flags:
        cols = ", ".join(f["column"] for f in profile.pii_flags)
        print(f"PII    : WARNING -> {cols}")
    else:
        print("PII    : none detected")
    print()
    hdr = f"{'COLUMN':<24} {'TYPE':<8} {'NONNULL':>8} {'MISS%':>7} {'UNIQUE':>8}"
    print(hdr)
    print("-" * len(hdr))
    for col in profile.columns:
        print(f"{col.name[:24]:<24} {col.dtype:<8} {col.count:>8} "
              f"{col.missing_pct:>7} {col.unique:>8}")


def _emit(obj, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(obj, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Auto-generate dataset cards, Croissant metadata, and datasheets.",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=["table", "json"], default="table",
                   help="output format (default: table)")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("profile", help="profile a dataset file")
    pp.add_argument("input", help="path to CSV/TSV/JSONL file")
    pp.add_argument("--name", help="override dataset name")

    cr = sub.add_parser("croissant", help="emit Croissant JSON-LD metadata")
    cr.add_argument("input")
    cr.add_argument("--name")

    cd = sub.add_parser("card", help="emit a HuggingFace-style dataset card (markdown)")
    cd.add_argument("input")
    cd.add_argument("--name")

    ds = sub.add_parser("datasheet", help="emit a Datasheets-for-Datasets skeleton")
    ds.add_argument("input")
    ds.add_argument("--name")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        name = getattr(args, "name", None)
        profile = profile_dataset(args.input, name=name)

        if args.command == "profile":
            if args.format == "json":
                _emit(profile.to_dict(), "json")
            else:
                _print_profile_table(profile)

        elif args.command == "croissant":
            doc = build_croissant(profile)
            if args.format == "json":
                _emit(doc, "json")
            else:
                print(json.dumps(doc, indent=2, default=str))

        elif args.command == "card":
            md = build_card_markdown(profile)
            if args.format == "json":
                _emit({"name": profile.name, "markdown": md}, "json")
            else:
                print(md)

        elif args.command == "datasheet":
            sheet = build_datasheet(profile)
            if args.format == "json":
                _emit(sheet, "json")
            else:
                print(f"# Datasheet for {sheet['dataset']}\n")
                for section, body in sheet["sections"].items():
                    print(f"## {section}")
                    print(f"_{body['question']}_")
                    print(body["answer"])
                    print()
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
