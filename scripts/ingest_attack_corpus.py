"""
ingest_attack_corpus.py — MITRE ATT&CK STIX corpus ingest into Chroma.

Fetches the official MITRE ATT&CK Enterprise STIX 2.1 bundle, parses every
technique and sub-technique, builds rich natural-language documents from:
  - Technique name + ID + tactic(s)
  - Full description
  - Procedure examples (real-world usage paragraphs)
  - Mitigation relationships
  - Detection guidance

Embeds via the project's Ollama embed model and upserts into a dedicated
``attack_techniques`` Chroma collection.  Existing vectors are overwritten
on re-run (idempotent upsert).

Usage:
    uv run python scripts/ingest_attack_corpus.py
    uv run python scripts/ingest_attack_corpus.py --dry-run     # parse only, no embed
    uv run python scripts/ingest_attack_corpus.py --local path/to/enterprise-attack.json

MITRE ATT&CK data is published under the Creative Commons Attribution 4.0
International license. https://attack.mitre.org/resources/terms-of-use/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

_STIX_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)
_COLLECTION = "attack_techniques"
_EMBED_BATCH = 10          # techniques per Ollama embed batch (descriptions can be long)
_MIN_DESC_LEN = 40         # skip technique stubs with no real description
_MAX_DOC_CHARS = 2000      # mxbai-embed-large context limit (~512 tokens); truncate beyond this

# Add project root to sys.path so backend imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# STIX parsing helpers
# ---------------------------------------------------------------------------

def _technique_id(obj: dict[str, Any]) -> str | None:
    """Extract T-number from external_references (e.g. T1059.001)."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id", "")
    return None


def _tactics(obj: dict[str, Any]) -> list[str]:
    """Extract kill-chain phase names (tactic names)."""
    return [
        phase["phase_name"].replace("-", " ").title()
        for phase in obj.get("kill_chain_phases", [])
        if phase.get("kill_chain_name") == "mitre-attack"
    ]


def _clean(text: str) -> str:
    """Strip STIX citation markers like (Citation: ...) and excessive whitespace."""
    text = re.sub(r"\(Citation:[^)]+\)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_index(bundle: dict[str, Any]) -> dict[str, list[dict]]:
    """
    Index all STIX objects by type for fast lookups.
    Returns dict keyed by STIX type.
    """
    index: dict[str, list[dict]] = {}
    for obj in bundle.get("objects", []):
        t = obj.get("type", "")
        index.setdefault(t, []).append(obj)
    return index


def parse_techniques(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Parse all attack-pattern objects (techniques + sub-techniques) from
    the STIX bundle.  Returns list of dicts ready for embedding.
    """
    index = _build_index(bundle)

    # Build ID → object maps
    obj_by_id: dict[str, dict] = {o["id"]: o for o in bundle.get("objects", [])}

    # Build technique_id → procedure examples (relationship type: uses)
    # Procedure examples are usage paragraphs from real threat groups / software
    procedure_by_technique: dict[str, list[str]] = {}
    for rel in index.get("relationship", []):
        if rel.get("relationship_type") != "uses":
            continue
        target_id = rel.get("target_ref", "")
        desc = rel.get("description", "")
        if target_id and desc:
            procedure_by_technique.setdefault(target_id, []).append(_clean(desc))

    # Build technique_id → mitigation names
    mitigations_by_technique: dict[str, list[str]] = {}
    for rel in index.get("relationship", []):
        if rel.get("relationship_type") != "mitigates":
            continue
        target_id = rel.get("target_ref", "")
        source_obj = obj_by_id.get(rel.get("source_ref", ""), {})
        mit_name = source_obj.get("name", "")
        if target_id and mit_name:
            mitigations_by_technique.setdefault(target_id, []).append(mit_name)

    techniques = []
    for obj in index.get("attack-pattern", []):
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        tid = _technique_id(obj)
        if not tid or not tid.startswith("T"):
            continue

        name = obj.get("name", "")
        description = _clean(obj.get("description", ""))
        if len(description) < _MIN_DESC_LEN:
            continue  # stub entry — skip

        tactics = _tactics(obj)
        detection = _clean(obj.get("x_mitre_detection", "") or "")
        platforms = obj.get("x_mitre_platforms", [])
        is_subtechnique = obj.get("x_mitre_is_subtechnique", False)
        procedures = procedure_by_technique.get(obj["id"], [])[:5]  # cap at 5 examples
        mitigations = mitigations_by_technique.get(obj["id"], [])

        # Build the document text — rich, structured for semantic search
        sections: list[str] = [
            f"Technique: {tid} — {name}",
            f"Tactics: {', '.join(tactics) if tactics else 'Unknown'}",
            f"Platforms: {', '.join(platforms) if platforms else 'Unknown'}",
            "",
            "Description:",
            description,
        ]
        if detection:
            sections += ["", "Detection guidance:", detection]
        if mitigations:
            sections += ["", "Mitigations: " + "; ".join(mitigations)]
        if procedures:
            sections += ["", "Observed in the wild:"]
            for proc in procedures:
                sections.append(f"- {proc[:400]}")  # truncate very long procedure examples

        document = "\n".join(sections)[:_MAX_DOC_CHARS]  # truncate to embedding model limit

        techniques.append(
            {
                "stix_id": obj["id"],
                "tid": tid,
                "name": name,
                "tactics": tactics,
                "platforms": platforms,
                "is_subtechnique": is_subtechnique,
                "document": document,
            }
        )

    # Sort by T-number for deterministic ordering
    techniques.sort(key=lambda x: x["tid"])
    return techniques


# ---------------------------------------------------------------------------
# Fetch / load bundle
# ---------------------------------------------------------------------------

async def fetch_bundle(url: str) -> dict[str, Any]:
    """Download the ATT&CK STIX bundle.  Shows progress."""
    print(f"[*] Fetching ATT&CK STIX bundle from {url} ...")
    t0 = time.time()
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    elapsed = time.time() - t0
    n = len(data.get("objects", []))
    print(f"[+] Downloaded {n:,} STIX objects in {elapsed:.1f}s")
    return data


def load_bundle(path: str) -> dict[str, Any]:
    """Load ATT&CK STIX bundle from a local file."""
    print(f"[*] Loading ATT&CK STIX bundle from {path} ...")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n = len(data.get("objects", []))
    print(f"[+] Loaded {n:,} STIX objects")
    return data


# ---------------------------------------------------------------------------
# Embed + upsert
# ---------------------------------------------------------------------------

async def embed_and_upsert(
    techniques: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> None:
    """Embed technique documents and upsert into Chroma attack_techniques collection."""
    # Late import so --dry-run doesn't need the full stack running
    from backend.core.config import settings
    from backend.services.ollama_client import OllamaClient
    from backend.stores.chroma_store import ChromaStore

    chroma = ChromaStore(
        data_dir=settings.DATA_DIR,
        chroma_url=settings.CHROMA_URL,
        chroma_token=settings.CHROMA_TOKEN,
    )

    # Ensure collection exists with cosine similarity space
    await chroma.get_or_create_collection_async(
        _COLLECTION,
        metadata={
            "embed_model": settings.OLLAMA_EMBED_MODEL,
            "hnsw:space": "cosine",
            "source": "mitre-attack-enterprise",
            "description": "MITRE ATT&CK Enterprise techniques for RAG context",
        },
    )
    print(f"[+] Chroma collection '{_COLLECTION}' ready")

    total = len(techniques)
    embedded = 0
    failed = 0

    async with OllamaClient(
        base_url=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
    ) as ollama:
        # Process in batches
        for batch_start in range(0, total, _EMBED_BATCH):
            batch = techniques[batch_start : batch_start + _EMBED_BATCH]
            batch_texts = [t["document"] for t in batch]

            batch_num = batch_start // _EMBED_BATCH + 1
            batch_total = (total + _EMBED_BATCH - 1) // _EMBED_BATCH
            print(
                f"  Batch {batch_num}/{batch_total} "
                f"({batch[0]['tid']}-{batch[-1]['tid']}) ...",
                end="",
                flush=True,
            )

            vectors = await ollama.embed_batch(batch_texts)

            # Filter out any failed embeddings (empty vector)
            ids, docs, metas, vecs = [], [], [], []
            for tech, vec in zip(batch, vectors):
                if not vec:
                    failed += 1
                    continue
                ids.append(tech["tid"])           # use T-number as stable Chroma ID
                docs.append(tech["document"])
                metas.append(
                    {
                        "tid": tech["tid"],
                        "name": tech["name"],
                        "tactics": ", ".join(tech["tactics"]),
                        "platforms": ", ".join(tech["platforms"]),
                        "is_subtechnique": str(tech["is_subtechnique"]),
                        "source": "mitre-attack",
                    }
                )
                vecs.append(vec)

            if ids and not dry_run:
                await chroma.add_documents_async(
                    collection_name=_COLLECTION,
                    ids=ids,
                    documents=docs,
                    embeddings=vecs,
                    metadatas=metas,
                )

            embedded += len(ids)
            print(f" ok ({len(ids)} upserted)")

    print()
    print(f"[+] Done — {embedded}/{total} techniques embedded", end="")
    if failed:
        print(f", {failed} failed (empty embedding — check Ollama)", end="")
    if dry_run:
        print(" [DRY RUN — nothing written to Chroma]", end="")
    print()

    if not dry_run:
        # Verify count
        chroma2 = ChromaStore(
            data_dir=settings.DATA_DIR,
            chroma_url=settings.CHROMA_URL,
            chroma_token=settings.CHROMA_TOKEN,
        )
        count = await chroma2.count_async(_COLLECTION)
        print(f"[+] Chroma '{_COLLECTION}' collection now has {count} documents")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest MITRE ATT&CK STIX corpus into Chroma for RAG context"
    )
    parser.add_argument(
        "--local",
        metavar="PATH",
        help="Load STIX bundle from local file instead of fetching from GitHub",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print stats without embedding or writing to Chroma",
    )
    parser.add_argument(
        "--url",
        default=_STIX_URL,
        help=f"URL to fetch STIX bundle from (default: {_STIX_URL})",
    )
    args = parser.parse_args()

    # Load bundle
    if args.local:
        bundle = load_bundle(args.local)
    else:
        bundle = await fetch_bundle(args.url)

    # Parse
    print("[*] Parsing techniques ...")
    techniques = parse_techniques(bundle)
    print(f"[+] Parsed {len(techniques)} active techniques / sub-techniques")

    # Print tactic breakdown
    tactic_counts: dict[str, int] = {}
    for t in techniques:
        for tac in t["tactics"]:
            tactic_counts[tac] = tactic_counts.get(tac, 0) + 1
    print("\n  Tactic breakdown:")
    for tac, count in sorted(tactic_counts.items()):
        print(f"    {tac:<35} {count:>4} techniques")

    if args.dry_run:
        print("\n[DRY RUN] Skipping embed and Chroma upsert.")
        print(f"\nSample document for {techniques[0]['tid']}:")
        print("-" * 60)
        print(techniques[0]["document"][:800])
        print("-" * 60)
        return

    print()
    await embed_and_upsert(techniques, dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
