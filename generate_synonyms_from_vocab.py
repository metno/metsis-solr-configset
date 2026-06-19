#!/usr/bin/env python3
"""Generate Solr synonyms.txt entries from a SKOS TTL vocabulary.

This script reads SKOS concept groups (collections), then for each concept emits
an equivalent synonym rule using prefLabel + altLabel values, e.g.:

    term_a, term_b, term_c

Equivalent rules are suitable for synonym expansion on query-time analyzers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

try:
    from rdflib import RDF, Graph, Literal, Namespace
    from rdflib.namespace import SKOS
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "rdflib is required. Install with: pip install rdflib\n"
        f"Import error: {exc}"
    )

ISOTHES = Namespace("http://purl.org/iso25964/skos-thes#")


def _normalize_label(value: str) -> str:
    return " ".join(value.split()).strip()


def _escape_for_solr_synonyms(value: str) -> str:
    # Escape the separator characters used by synonyms.txt syntax.
    return value.replace("\\", "\\\\").replace(",", "\\,")


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _literal_lang_ok(lit: Literal, lang: str | None) -> bool:
    if lang is None:
        return True
    lit_lang = (lit.language or "").lower()
    return lit_lang == lang.lower()


def _get_group_display_label(graph: Graph, group_uri, lang: str | None) -> str:
    labels = [
        str(label)
        for label in graph.objects(group_uri, SKOS.prefLabel)
        if isinstance(label, Literal) and _literal_lang_ok(label, lang)
    ]
    if not labels:
        labels = [str(label) for label in graph.objects(group_uri, SKOS.prefLabel)]
    if labels:
        return _normalize_label(labels[0])
    return str(group_uri)


def _get_concept_labels(graph: Graph, concept_uri, lang: str | None) -> list[str]:
    labels: list[str] = []
    for predicate in (SKOS.prefLabel, SKOS.altLabel):
        for lit in graph.objects(concept_uri, predicate):
            if not isinstance(lit, Literal):
                continue
            if not _literal_lang_ok(lit, lang):
                continue
            normalized = _normalize_label(str(lit))
            if normalized:
                labels.append(normalized)

    if not labels and lang is not None:
        for predicate in (SKOS.prefLabel, SKOS.altLabel):
            for lit in graph.objects(concept_uri, predicate):
                if isinstance(lit, Literal):
                    normalized = _normalize_label(str(lit))
                    if normalized:
                        labels.append(normalized)

    return _dedupe_preserve_order(labels)


def build_synonym_lines(ttl_path: Path, lang: str | None) -> list[str]:
    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    groups = {
        subject
        for subject in graph.subjects(RDF.type, SKOS.Collection)
    }
    groups.update(
        subject
        for subject in graph.subjects(RDF.type, ISOTHES.ConceptGroup)
    )

    lines: list[str] = []

    ordered_groups = sorted(
        groups,
        key=lambda uri: _get_group_display_label(graph, uri, lang).casefold(),
    )

    for group_uri in ordered_groups:
        group_label = _get_group_display_label(graph, group_uri, lang)
        lines.append(f"# Group: {group_label}")

        members = list(graph.objects(group_uri, SKOS.member))
        if not members:
            lines.append("# (no members)")
            lines.append("")
            continue

        concept_lines: list[str] = []
        for concept_uri in members:
            labels = _get_concept_labels(graph, concept_uri, lang)
            if len(labels) < 2:
                continue
            escaped = [_escape_for_solr_synonyms(label) for label in labels]
            concept_lines.append(", ".join(escaped))

        concept_lines = sorted(set(concept_lines), key=str.casefold)

        if concept_lines:
            lines.extend(concept_lines)
        else:
            lines.append("# (no synonym expansions with >=2 labels)")

        lines.append("")

    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Solr synonyms.txt equivalent rules from SKOS prefLabel/altLabel "
            "grouped by vocabulary collections."
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
    args = parse_args()

    ttl_path: Path = args.ttl_path
    if not ttl_path.exists():
        print(f"Input file not found: {ttl_path}", file=sys.stderr)
        return 2

    lang = None if str(args.lang).lower() == "all" else str(args.lang).lower()
    lines = build_synonym_lines(ttl_path=ttl_path, lang=lang)
    output_text = "\n".join(lines).rstrip() + "\n"

    if args.output is None:
        sys.stdout.write(output_text)
    else:
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
