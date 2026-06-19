#!/usr/bin/env bash
set -euo pipefail

SOLR_BASE_URL="${SOLR_BASE_URL:-http://localhost:8983/solr}"
SOLR_CORE="${SOLR_CORE:-adc}"
INPUT_FILE="${INPUT_FILE:-example_mmd_solr.json}"
THUMBNAIL_URL="${THUMBNAIL_URL:-https://example.org/thumbnail.png}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for this test" >&2
  exit 1
fi

if [[ ! -f "${INPUT_FILE}" ]]; then
  echo "Input file not found: ${INPUT_FILE}" >&2
  exit 1
fi

doc_id="$(jq -r '.[0].id' "${INPUT_FILE}")"
if [[ -z "${doc_id}" || "${doc_id}" == "null" ]]; then
  echo "Could not read id from first document in ${INPUT_FILE}" >&2
  exit 1
fi

solr_core_url="${SOLR_BASE_URL}/${SOLR_CORE}"

wait_for_solr() {
  local max_retries=30
  local i
  for ((i = 1; i <= max_retries; i++)); do
    if curl -fsS --max-time 5 "${solr_core_url}/select?wt=json&q=*:*&rows=0" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Solr core '${SOLR_CORE}' did not become ready in time" >&2
  return 1
}

fetch_doc() {
  curl -fsS "${solr_core_url}/select?wt=json&q=id:${doc_id}&rows=1"
}

normalize_doc() {
  jq -S '
    def norm:
      if type == "object" then
        with_entries(select(.key != "_root_" and .key != "_version_"))
        | map_values(norm)
      elif type == "array" then
        map(norm)
      else
        .
      end;
    norm
  '
}

echo "Waiting for Solr core to be ready..."
wait_for_solr

echo "Indexing ${INPUT_FILE} using Solr update API..."
if ! curl -fsS \
  -H 'Content-Type: application/json' \
  --data-binary "@${INPUT_FILE}" \
  "${solr_core_url}/update?commit=true" >/dev/null; then
  echo "Failed to index ${INPUT_FILE}, retrying without -f to show error:" >&2
  curl -sS \
    -H 'Content-Type: application/json' \
    --data-binary "@${INPUT_FILE}" \
    "${solr_core_url}/update?commit=true"
  exit 1
fi

echo "Fetching indexed document..."
indexed_response="$(fetch_doc)"

num_found="$(jq -r '.response.numFound' <<<"${indexed_response}")"
if [[ "${num_found}" != "1" ]]; then
  echo "Expected 1 document for id=${doc_id}, got ${num_found}" >&2
  exit 1
fi

input_doc_norm="$(jq '.[0]' "${INPUT_FILE}" | normalize_doc)"
indexed_doc_norm="$(jq '.response.docs[0]' <<<"${indexed_response}" | normalize_doc)"

if [[ "${input_doc_norm}" != "${indexed_doc_norm}" ]]; then
  echo "Indexed document differs from input (ignoring _root_ and _version_)" >&2
  diff <(jq -S . <<<"${input_doc_norm}") <(jq -S . <<<"${indexed_doc_norm}") || true
  exit 1
fi

echo "Applying atomic update (isChild=false, thumbnail_url=${THUMBNAIL_URL})..."
atomic_payload="$(jq -n \
  --arg id "${doc_id}" \
  --arg thumbnail_url "${THUMBNAIL_URL}" \
  '[{
    id: $id,
    isChild: { set: false },
    thumbnail_url: { set: $thumbnail_url }
  }]'
)"

curl -fsS \
  -H 'Content-Type: application/json' \
  --data-binary "${atomic_payload}" \
  "${solr_core_url}/update?commit=true" >/dev/null

echo "Fetching document after atomic update..."
updated_response="$(fetch_doc)"
updated_doc="$(jq '.response.docs[0]' <<<"${updated_response}")"

updated_is_child="$(jq -r '.isChild' <<<"${updated_doc}")"
updated_thumbnail_url="$(jq -r '.thumbnail_url' <<<"${updated_doc}")"

if [[ "${updated_is_child}" != "false" ]]; then
  echo "Atomic update failed: expected isChild=false, got ${updated_is_child}" >&2
  exit 1
fi

if [[ "${updated_thumbnail_url}" != "${THUMBNAIL_URL}" ]]; then
  echo "Atomic update failed: expected thumbnail_url=${THUMBNAIL_URL}, got ${updated_thumbnail_url}" >&2
  exit 1
fi

before_unchanged_norm="$(jq 'del(.isChild, .thumbnail_url)' <<<"${indexed_doc_norm}" | normalize_doc)"
after_unchanged_norm="$(jq 'del(.isChild, .thumbnail_url)' <<<"${updated_doc}" | normalize_doc)"

if [[ "${before_unchanged_norm}" != "${after_unchanged_norm}" ]]; then
  echo "Atomic update changed fields other than isChild/thumbnail_url" >&2
  diff <(jq -S . <<<"${before_unchanged_norm}") <(jq -S . <<<"${after_unchanged_norm}") || true
  exit 1
fi

echo "Atomic update test passed."
