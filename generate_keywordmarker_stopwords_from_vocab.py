#!/usr/bin/env python3
"""Generate Solr stopwords.txt entries from a SKOS TTL vocabulary.

This script reads SKOS concepts and extracts all prefLabel values,
outputting them as individual entries suitable for use with Solr's
KeywordMarkerFilter.

Each line in the output corresponds to a preferred label (prefLabel) of a concept.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

try:
    from rdflib import Graph, Literal, Namespace
    from rdflib.namespace import SKOS
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "rdflib is required. Install with: pip install rdflib\n"
        f"Import error: {exc}"
    )

ISOTHES = Namespace("http://purl.org/iso25964/skos-thes#")


def _normalize_label(value: str) -> str:
    """Normalize label by stripping extra spaces."""
    return " ".join(value.split()).strip()


def _literal_lang_ok(lit: Literal, lang: str | None) -> bool:
    """Check if the literal matches the desired language."""
    if lang is None:
        return True
    lit_lang = (lit.language or "").lower()
    return lit_lang == lang.lower()


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    """Deduplicate items while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def extract_preferred_labels(ttl_path: Path, lang: str | None) -> list[str]:
    """Extract all preferred labels (skos:prefLabel) from the SKOS TTL file."""
    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    labels: list[str] = []

    # Iterate over all concepts in the graph
    for concept_uri in graph.subjects(None, None):
        for lit in graph.objects(concept_uri, SKOS.prefLabel):
            if not isinstance(lit, Literal):
                continue
            if not _literal_lang_ok(lit, lang):
                continue

            # Normalize and add the label
            normalized = _normalize_label(str(lit))
            if normalized:
                labels.append(normalized)

    # Deduplicate labels while preserving order
    return _dedupe_preserve_order(labels)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate Solr stopwords.txt equivalent rules from SKOS prefLabel "
            "values for use with KeywordMarkerFilter."
        )
    )
    parser.add_argument(
        "ttl_path",
        type=Path,
        help="Path to mmd_vocabulary.ttl (or another SKOS Turtle file)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--lang",
        default="en",
        help=(
            "Preferred label language tag (default: en). Use '--lang all' to include "
            "all languages."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Main script execution."""
    args = parse_args()

    ttl_path: Path = args.ttl_path
    if not ttl_path.exists():
        print(f"Input file not found: {ttl_path}", file=sys.stderr)
        return 2

    # Determine the language filter
    lang = None if str(args.lang).lower() == "all" else str(args.lang).lower()

    # Extract preferred labels
    labels = extract_preferred_labels(ttl_path=ttl_path, lang=lang)
    output_text = "\n".join(labels).rstrip() + "\n"

    # Write to output
    if args.output is None:
        sys.stdout.write(output_text)
    else:
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
