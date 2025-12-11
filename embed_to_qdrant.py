#!/usr/bin/env python3
"""
embed_to_qdrant.py

Create text embeddings with Vertex AI (Gemini) and upsert to Qdrant.

What this version does
- Uses **category** metadata (from front-matter `category`) instead of `project`.
- Qdrant payload fields:
    • people  ← front-matter `attendees`  (synonyms: `people`, `participants`)
    • tags    ← front-matter `tags`       (synonym:  `tag`)
    • category← front-matter `category`   (CLI can override; falls back to FM `project` or the parent folder)
    • type    ← CLI `--type` → FM `type` → FM `category`/`tags` → folder heuristic (one-on-one|meeting|email|slack|calendar|note)
- Robust front-matter parsing (tolerates BOM/leading whitespace + CRLF).
- Deterministic UUIDv5 point IDs (Qdrant accepts int/UUID).
- Freshness fields: `doc_version` (content hash), `ingested_at`, `source_mtime`.
- **Independent duplicate checking**:
    • Early Qdrant connection verification (fails fast if unavailable)
    • Per-document duplicate check: skips if same doc_id + same content hash (unless --force)
    • Global duplicate detection: warns if same content hash exists in other documents
    • Tombstoning of prior chunks (`is_active:false`) or hard delete with flag
- Skip unchanged files unless `--force` or `--no-skip-if-unchanged`.
- **Multi-input modes**:
    • Single file: positional or `--path` (backward compatible)
    • Batch: `--input` (repeatable files/dirs), `--recursive`, `--ext md,txt`
    • Streaming: `--stdin` (newline-separated paths)
- **Stable doc IDs across locations**:
    • `--doc-id-key uid` (prefer a front-matter key if present)
    • `--vault-root /path/to/vault` (use RELATIVE path under this root)
    • Fallback to absolute path (original behavior)
- Emits JSON (single result or batch summary).

Requirements:
  pip install qdrant-client google-cloud-aiplatform pyyaml

Auth (once):
  gcloud auth application-default login --project <your-gcp-project>

Examples:

Single file (original):
  ./.venv/bin/python embed_to_qdrant.py \
    --path "/Users/erik/Obsidian/RedHat+/Process/meetings/2025-10-24 - AWS PM.md" \
    --type meeting --category "sync-meeting" --force

Batch folders (recursive), infer type/category from folders:
  ./.venv/bin/python embed_to_qdrant.py \
    --input "/Users/erik/Obsidian/RedHat+/Process/meetings" \
    --input "/Users/erik/Obsidian/RedHat+/Process/one-on-one" \
    --input "/Users/erik/Obsidian/RedHat+/Email" \
    --recursive --ext md,txt \
    --collection personal_assistant \
    --vault-root "/Users/erik/Obsidian" \
    --debug
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------- CONFIG (defaults; override via env vars) ----------------
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "cee-gcp-dxp")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Embedding model (Vertex AI Text Embeddings)
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

# Qdrant (local default)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "personal_assistant")

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Deterministic UUID namespace for stable IDs across runs
UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "erik-newby/personal-assistant")
# -------------------------------------------------------------------------

# ----- Front-matter parsing (YAML preferred) -----
try:
    import yaml  # pip install pyyaml
except Exception:
    yaml = None  # We'll still attempt a naive fallback

# Allow optional BOM/whitespace before '---', and \r?\n newlines.
FM_RE = re.compile(r"^\ufeff?\s*---\r?\n(.*?)\r?\n---\s*\r?\n?", re.DOTALL)


def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """
    Return (front_matter_dict, remainder_text).
    If PyYAML isn't available, naive parse is used (best-effort).
    """
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    rest = text[m.end():]
    if yaml:
        try:
            data = yaml.safe_load(raw) or {}
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    else:
        data = {}
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    return data, rest


def listify(val: Any) -> List[str]:
    """Normalize any front-matter field to a list[str]."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    s = str(val).strip()
    if not s:
        return []
    # Strip surrounding brackets if provided as a YAML-ish string: "[a, b]"
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return [x.strip() for x in s.split(",") if x.strip()]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_vector_name(model_name: str) -> str:
    """Convert model name to valid vector name (replace special chars with underscores)."""
    return model_name.replace("-", "_").replace("@", "_").replace(".", "_")


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def guess_title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        t = line.strip()
        if t.startswith("# "):
            return t[2:].strip()
        if t.lower().startswith("title:"):
            return t.split(":", 1)[1].strip()
    return Path(fallback).stem


def chunk_text(text: str, max_chars: int, overlap: int) -> List[str]:
    """Paragraph-based chunking with character overlap."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        return [text]
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    def flush():
        if cur:
            chunks.append("\n\n".join(cur))

    for p in paras:
        plen = len(p) + (2 if cur else 0)
        if cur_len + plen <= max_chars:
            cur.append(p)
            cur_len += plen
        else:
            flush()
            if overlap > 0 and chunks:
                tail = chunks[-1]
                keep = tail[-overlap:]
                cur = [keep, p]
                cur_len = len(keep) + len(p) + 2
            else:
                cur = [p]
                cur_len = len(p)
    flush()
    return chunks


def stable_uuid5(*parts: str) -> uuid.UUID:
    """Create a stable UUIDv5 from concatenated parts using a fixed namespace."""
    name = "|".join(parts)
    return uuid.uuid5(UUID_NAMESPACE, name)


def infer_type_from_frontmatter(fm: Dict[str, Any], tags: List[str]) -> Optional[str]:
    """
    Infer document type from front-matter category and tags.
    Returns type string if found, None if not determinable from front-matter.
    
    Priority:
    1. category field (e.g., "one-on-one" → type "one-on-one")
    2. tags field (check for type indicators)
    """
    # Check category field first (highest priority)
    category = fm.get("category") or fm.get("project")  # project is legacy synonym
    if category:
        cat_str = str(category).lower().strip()
        # Direct category-to-type mappings
        if cat_str == "one-on-one" or cat_str == "one-on-ones":
            return "one-on-one"
        # Meeting categories: any category that isn't one-on-one, email, slack, calendar is likely a meeting
        # Common meeting categories might include: "sync-meeting", "standup", "retro", etc.
        # If category exists and isn't one of the other types, assume it's a meeting
        if cat_str not in ["email", "emails", "slack", "calendar", "cal", "note", "notes"]:
            # Likely a meeting category (could be "sync-meeting", "standup", "retro", etc.)
            return "meeting"
    
    # Check tags for type indicators (case-insensitive)
    tag_lower = [str(t).lower().strip() for t in tags]
    
    # Check for explicit type tags
    if any(tag in ["one-on-one", "1-1", "one-on-ones"] for tag in tag_lower):
        return "one-on-one"
    if any(tag in ["meeting", "meetings"] for tag in tag_lower):
        return "meeting"
    if any(tag in ["email", "emails"] for tag in tag_lower):
        return "email"
    if any(tag in ["slack"] for tag in tag_lower):
        return "slack"
    if any(tag in ["calendar", "cal"] for tag in tag_lower):
        return "calendar"
    
    # No type found in front-matter
    return None


def infer_type_from_path(path: Path) -> str:
    """
    Fallback: Infer document type from file path.
    This is used as a last resort when front-matter doesn't provide type information.
    """
    s = str(path).lower()
    if "/one-on-one" in s or "/1-1" in s or "/one_on_one" in s:
        return "one-on-one"
    if "/meetings" in s or "/meeting" in s:
        return "meeting"
    if "/email" in s or "/emails" in s:
        return "email"
    if "/slack" in s:
        return "slack"
    if "/calendar" in s or "/cal" in s:
        return "calendar"
    return "note"


def fallback_category_from_path(path: Path) -> str:
    """
    If front-matter/CLI don't supply a category, fall back to the immediate
    parent folder name (e.g., meetings, one-on-one, email).
    """
    try:
        return path.parent.name
    except Exception:
        return ""


def collect_files(inputs: List[str], recursive: bool, exts: List[str]) -> List[Path]:
    want = {"." + e.strip().lstrip(".").lower() for e in exts if e.strip()}
    out: List[Path] = []
    for spec in inputs:
        p = Path(spec)
        if p.is_file():
            if not want or p.suffix.lower() in want:
                out.append(p)
        elif p.is_dir():
            if recursive:
                out.extend([f for f in p.rglob("*") if f.is_file() and (not want or f.suffix.lower() in want)])
            else:
                out.extend([f for f in p.glob("*") if f.is_file() and (not want or f.suffix.lower() in want)])
        else:
            # You can add glob support here if needed
            pass
    return out


# ----- Vertex AI / Embeddings -----
try:
    from vertexai import init as vertex_init
    try:
        # Newer path
        from vertexai.language_models import TextEmbeddingModel
    except ImportError:
        # Older SDK path
        from vertexai.preview.language_models import TextEmbeddingModel
except ImportError:
    print("Missing dependency: pip install google-cloud-aiplatform", file=sys.stderr)
    raise


def init_vertex_or_die():
    if not PROJECT:
        print("GOOGLE_CLOUD_PROJECT is required (env) or hardcode PROJECT.", file=sys.stderr)
        sys.exit(1)

    # Load credentials from file if specified, with proper scopes for Vertex AI
    credentials = None
    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("VERTEX_CREDENTIALS_FILE")
    if credentials_file and os.path.exists(credentials_file):
        try:
            import google.auth
            credentials, _ = google.auth.load_credentials_from_file(
                credentials_file,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except Exception as e:
            print(f"Warning: Failed to load credentials from {credentials_file}: {e}", file=sys.stderr)

    vertex_init(project=PROJECT, location=LOCATION, credentials=credentials)


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    embeddings = model.get_embeddings(texts)
    vecs = [e.values for e in embeddings]
    dims = {len(v) for v in vecs}
    if dims != {EMBED_DIM}:
        raise ValueError(
            f"Embedding dimension mismatch: got {list(dims)}; expected {EMBED_DIM}. "
            "Update EMBED_DIM or choose a model with that output size."
        )
    return vecs


# ----- Qdrant -----
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
        PointIdsList,
    )
except ImportError:
    print("Missing dependency: pip install qdrant-client", file=sys.stderr)
    raise


def ensure_collection(client: QdrantClient, name: str, dim: int, vector_name: str):
    """Create collection if missing; validate vector size if present.

    Uses named vectors for MCP server compatibility.
    """
    try:
        info = client.get_collection(name)
        # Try to read configured vector size; qdrant-client versions differ in shape
        cfg = getattr(info, "config", None) or (info.dict().get("config", {}) if hasattr(info, "dict") else {})
        params = cfg.get("params", {}) if isinstance(cfg, dict) else {}
        vectors = params.get("vectors", {})
        size = None
        # Check for named vector config
        if isinstance(vectors, dict):
            if vector_name in vectors:
                # Named vector exists
                vec_cfg = vectors[vector_name]
                size = vec_cfg.get("size") if isinstance(vec_cfg, dict) else getattr(vec_cfg, "size", None)
            elif "size" in vectors:
                # Unnamed vector (old format) - incompatible, need to recreate
                raise RuntimeError(
                    f"Collection '{name}' uses unnamed vectors but named vectors are required. "
                    f"Delete the collection and re-ingest: curl -X DELETE 'http://localhost:6333/collections/{name}'"
                )
        if size is not None and int(size) != dim:
            raise RuntimeError(
                f"Collection '{name}' exists with size={size}, but EMBED_DIM={dim}. "
                f"Use a different collection or recreate with the correct size."
            )
    except Exception as e:
        if "unnamed vectors" in str(e):
            raise
        # Not found (or couldn't parse): create with named vectors
        client.create_collection(
            collection_name=name,
            vectors_config={
                vector_name: VectorParams(size=dim, distance=Distance.COSINE),
            },
        )


def list_active_point_ids(client: QdrantClient, collection: str, doc_id: str) -> List[str]:
    """
    Find all active point IDs for a given doc_id.
    Used to identify existing embeddings that need to be tombstoned/deleted.
    """
    flt = Filter(
        must=[
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="is_active", match=MatchValue(value=True)),
        ]
    )
    out_ids: List[str] = []
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            scroll_filter=flt,
            limit=256,
            with_payload=False,
            with_vectors=False,
            offset=next_offset,
        )
        out_ids.extend([str(p.id) for p in points])
        if next_offset is None:
            break
    return out_ids


def check_content_hash_exists(client: QdrantClient, collection: str, content_hash: str, exclude_doc_id: str = "") -> bool:
    """
    Check if content with the same hash already exists in the collection.
    This provides a global duplicate check independent of document ID.
    
    Args:
        client: Qdrant client
        collection: Collection name
        content_hash: SHA1 hash of the document content
        exclude_doc_id: If provided, exclude points with this doc_id from the check
    
    Returns:
        True if active points with this content_hash exist (optionally excluding exclude_doc_id)
    """
    must_conditions = [
        FieldCondition(key="doc_version", match=MatchValue(value=content_hash)),
        FieldCondition(key="is_active", match=MatchValue(value=True)),
    ]
    
    # If excluding a doc_id, we want to find duplicates in OTHER documents
    # Note: We'll check if any exist, then filter in Python if needed
    # (Qdrant doesn't have direct "not equals" filter in all versions)
    
    flt = Filter(must=must_conditions)
    
    # Check if any points exist with this content hash
    # If exclude_doc_id is provided, we need to scroll through more points
    # to find one that's NOT from the excluded doc_id
    limit = 10 if exclude_doc_id else 1  # Check a few points if filtering by doc_id
    
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=flt,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    
    if points and isinstance(points, list):
        # If exclude_doc_id provided, check if ANY point is from a different doc
        if exclude_doc_id:
            for pt in points:
                payload = getattr(pt, "payload", {}) or {}
                pt_doc_id = payload.get("doc_id")
                if pt_doc_id and pt_doc_id != exclude_doc_id:
                    return True  # Found duplicate in another document
            return False  # Only found points from the excluded doc_id (no duplicate elsewhere)
        # No exclude_doc_id: any match means duplicate exists
        return True
    
    return False  # No points found with this content hash


def tombstone_points(client: QdrantClient, collection: str, ids: List[str]):
    if not ids:
        return
    client.set_payload(
        collection_name=collection,
        payload={"is_active": False, "archived_at": now_iso()},
        points=ids,
    )


def hard_delete_points(client: QdrantClient, collection: str, ids: List[str]):
    if not ids:
        return
    client.delete(collection_name=collection, points_selector=PointIdsList(points=ids))


# ----- Main per-file pipeline -----
def process_file(
    path: Path,
    ctype_cli: str,
    category_cli: str,
    force: bool,
    hard_delete_previous: bool,
    skip_if_unchanged: bool,
    collection_name: str,
    debug: bool,
    doc_id_key: str = "",
    vault_root: str = "",
) -> Dict[str, Any]:
    full_text = read_text(path)
    fm, body = parse_front_matter(full_text)
    title = guess_title(body or full_text, str(path))

    # Resolve people/tags STRICTLY from FM (with synonyms)
    people = listify(fm.get("attendees") or fm.get("people") or fm.get("participants"))
    tags = listify(fm.get("tags") or fm.get("tag"))

    # Category resolution with fallback to FM 'project' (compat) and path fallback
    category = category_cli or fm.get("category") or fm.get("project") or ""
    if not category:
        category = fallback_category_from_path(path)

    # Type resolution (CLI → FM type field → FM category/tags → path heuristic)
    # Updated to use category/tags from front-matter (matching process_one-on-one_notes.py pattern)
    ctype = ctype_cli or fm.get("type") or infer_type_from_frontmatter(fm, tags) or infer_type_from_path(path)

    source_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    content_sha = sha1(full_text)

    # ----- Stable doc identity -----
    # 1) If a front-matter key is specified and present (e.g., uid), prefer it.
    doc_key = None
    if doc_id_key:
        val = fm.get(doc_id_key)
        if val:
            doc_key = f"fm:{doc_id_key}:{str(val).strip()}"

    # 2) Else, if a vault root is provided and path is inside it, use RELATIVE path for stability.
    if doc_key is None and vault_root:
        try:
            rel = Path(path).resolve().relative_to(Path(vault_root).resolve())
            doc_key = f"rel:{str(rel)}"
        except Exception:
            pass

    # 3) Fallback: absolute path (original behavior)
    if doc_key is None:
        doc_key = str(Path(path).resolve())

    doc_uuid = stable_uuid5(doc_key)
    doc_id = str(doc_uuid)
    doc_version = content_sha

    if debug:
        debug_blob = {
            "file": str(path),
            "fm_raw_keys": list(fm.keys()),
            "resolved": {
                "type": ctype,
                "category": category,
                "people": people,
                "tags": tags,
                "doc_key": doc_key,
            },
        }
        print("[debug] front-matter + resolved metadata:", json.dumps(debug_blob, indent=2), file=sys.stderr)

    # ===== INITIALIZE CLIENTS EARLY (independent operation) =====
    # Initialize Vertex AI first (required for embeddings)
    init_vertex_or_die()

    # Get vector name for named vector config (MCP server compatibility)
    vector_name = get_vector_name(EMBED_MODEL)

    # Initialize and verify Qdrant connection early
    # This ensures the script fails fast if Qdrant is unavailable
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        # Verify connection by checking collection exists or creating it
        ensure_collection(client, collection_name, EMBED_DIM, vector_name)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Qdrant at {QDRANT_URL}: {e}") from e

    # ===== DUPLICATE CHECKING (independent of processing) =====
    # Strategy:
    # 1. Check if THIS document (doc_id) already exists with same content hash
    #    - If yes and unchanged: skip entire embedding process (optimization)
    # 2. Check globally if ANY document has the same content hash
    #    - If yes: log warning but proceed (content might legitimately appear in multiple places)
    # 3. Find existing active points for this doc_id
    #    - These will be tombstoned/deleted before upserting new ones
    
    # Check 1: Same doc_id + same content hash = skip (unchanged document)
    existing_active = list_active_point_ids(client, collection_name, doc_id)
    if skip_if_unchanged and existing_active and not force:
        pts, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                    FieldCondition(key="is_active", match=MatchValue(value=True)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if pts and isinstance(pts, list):
            payload0 = getattr(pts[0], "payload", {}) or {}
            if payload0.get("doc_version") == doc_version:
                if debug:
                    print(f"[debug] Skipping unchanged document: {path} (doc_id={doc_id}, hash={doc_version[:8]}...)", file=sys.stderr)
                return {
                    "status": "skipped_unchanged",
                    "collection": collection_name,
                    "doc_id": doc_id,
                    "title": title,
                    "path": str(path),
                }
    
    # Check 2: Global duplicate check (same content hash exists elsewhere)
    # This is informational - we still proceed because the same content might
    # legitimately exist in multiple documents (e.g., templates, copies)
    duplicate_exists = check_content_hash_exists(client, collection_name, doc_version, exclude_doc_id=doc_id)
    if duplicate_exists:
        if debug:
            print(f"[debug] WARNING: Content hash {doc_version[:8]}... already exists in another document", file=sys.stderr)

    # ===== PROCESSING STAGE =====
    # Only reach here if:
    # - Document is new, OR
    # - Document content changed (different hash), OR
    # - --force flag was used
    
    # Chunk + embed
    chunks = chunk_text(body or full_text, CHUNK_SIZE, CHUNK_OVERLAP)
    vectors = embed_texts(chunks)

    # ===== CLEANUP PREVIOUS VERSION =====
    # If this doc_id had previous embeddings, remove them before upserting new ones.
    # This prevents orphaned/duplicate chunks from old versions.
    # Note: existing_active was already computed during duplicate checking above.
    if existing_active:
        if hard_delete_previous:
            if debug:
                print(f"[debug] Hard deleting {len(existing_active)} previous points for doc_id={doc_id}", file=sys.stderr)
            hard_delete_points(client, collection_name, existing_active)
        else:
            if debug:
                print(f"[debug] Tombstoning {len(existing_active)} previous points for doc_id={doc_id}", file=sys.stderr)
            tombstone_points(client, collection_name, existing_active)

    # Upsert new points (UUID string ids)
    ingested_at = now_iso()
    points: List[PointStruct] = []
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        pid = str(stable_uuid5(doc_id, str(idx)))
        payload = {
            "document": chunk,        # <-- chunk text for MCP server compatibility
            "type": ctype,
            "category": category,
            "title": title,
            "path": str(path),
            "doc_id": doc_id,
            "doc_version": doc_version,
            "chunk_idx": idx,
            "chunk_chars": len(chunk),
            "people": people,         # from FM attendees/people/participants
            "tags": tags,             # from FM tags/tag
            "is_active": True,
            "ingested_at": ingested_at,
            "source_mtime": source_mtime,
            "content_sha": content_sha,
        }
        # Use named vector for MCP server compatibility
        points.append(PointStruct(id=pid, vector={vector_name: vec}, payload=payload))

    client.upsert(collection_name=collection_name, points=points)

    return {
        "status": "ok",
        "collection": collection_name,
        "embedded_chunks": len(points),
        "doc_id": doc_id,
        "title": title,
        "path": str(path),
        "model": EMBED_MODEL,
        "embed_dim": EMBED_DIM,
        "people_from_front_matter": people,
        "tags_from_front_matter": tags,
        "category": category,
        "type": ctype,
    }


# ----- CLI -----
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Vertex → Qdrant embedding with freshness, tombstones & batch modes")

    # Single-file compatibility (as before)
    ap.add_argument("positional_path", nargs="?", help="Path to .md/.txt (positional)")
    ap.add_argument("--path", help="Path to .md/.txt")

    # NEW: batch inputs
    ap.add_argument("--input", action="append",
                    help="File or directory to process (can repeat). If directory, combine with --recursive.")
    ap.add_argument("--recursive", action="store_true", help="Recurse into directories specified by --input.")
    ap.add_argument("--ext", default="md,txt",
                    help="Comma-separated list of file extensions to include (default: md,txt).")
    ap.add_argument("--stdin", action="store_true",
                    help="Read newline-separated file paths from STDIN (combined with --input if both used).")

    # CLI overrides for type/category (people & tags come strictly from front-matter)
    ap.add_argument("--type", default="", help="note|meeting|one-on-one|email|calendar|slack (overrides FM/heuristics)")
    ap.add_argument("--category", default="", help="Category (overrides front-matter 'category').")

    # Doc ID behavior
    ap.add_argument("--doc-id-key", default="", help="Front-matter key to use as logical doc ID (e.g., uid).")
    ap.add_argument("--vault-root", default=os.getenv("VAULT_ROOT", ""),
                    help="If set, doc_id uses path relative to this folder (for stability across watchers).")

    # Ingestion switches
    ap.add_argument("--force", action="store_true", help="Force re-embed even if unchanged")
    ap.add_argument("--hard-delete-previous", action="store_true", help="Physically delete prior version")
    ap.add_argument("--no-skip-if-unchanged", action="store_true", help="Always embed even if content hash is same")
    ap.add_argument("--collection",
                    default=os.getenv("QDRANT_COLLECTION", QDRANT_COLLECTION),
                    help="Qdrant collection (env QDRANT_COLLECTION or default)")
    ap.add_argument("--debug", action="store_true", help="Print parsed front-matter and resolved metadata")
    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()

    # Gather inputs
    inputs: List[str] = []
    if args.input:
        inputs.extend(args.input)
    if args.stdin:
        stdin_text = sys.stdin.read()
        for line in stdin_text.splitlines():
            s = line.strip()
            if s:
                inputs.append(s)

    # Back-compat: single path (positional or --path)
    single_path = args.path or args.positional_path

    # Decide processing mode
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if inputs:
        files = collect_files(inputs, recursive=args.recursive, exts=[e for e in args.ext.split(",") if e.strip()])
        if not files and not single_path:
            print(json.dumps({"status": "no_inputs_found", "inputs": inputs}), file=sys.stderr)
            sys.exit(3)
        # Process batch first
        for f in files:
            try:
                res = process_file(
                    path=f,
                    ctype_cli=args.type,
                    category_cli=args.category,
                    force=args.force,
                    hard_delete_previous=args.hard_delete_previous,
                    skip_if_unchanged=not args.no_skip_if_unchanged,
                    collection_name=args.collection,
                    debug=args.debug,
                    doc_id_key=args.doc_id_key,
                    vault_root=args.vault_root,
                )
                results.append(res)
            except Exception as e:
                errors.append({"path": str(f), "error": str(e)})
        # If a single_path was also supplied, process it too (for compatibility)
        if single_path:
            p = Path(single_path)
            if not p.exists():
                print(f"File not found: {p}", file=sys.stderr)
                sys.exit(2)
            try:
                res = process_file(
                    path=p,
                    ctype_cli=args.type,
                    category_cli=args.category,
                    force=args.force,
                    hard_delete_previous=args.hard_delete_previous,
                    skip_if_unchanged=not args.no_skip_if_unchanged,
                    collection_name=args.collection,
                    debug=args.debug,
                    doc_id_key=args.doc_id_key,
                    vault_root=args.vault_root,
                )
                results.append(res)
            except Exception as e:
                errors.append({"path": str(p), "error": str(e)})
        summary = {
            "status": "ok_with_errors" if errors else "ok",
            "count_processed": len(results),
            "count_errors": len(errors),
            "collection": args.collection,
            "model": EMBED_MODEL,
            "embed_dim": EMBED_DIM,
            "items": results,
            "errors": errors,
        }
        print(json.dumps(summary, indent=2))
        # Non-zero exit if any errors (helps CI/automation), but still prints all successes.
        sys.exit(0 if not errors else 1)

    # Single-file mode (original flow)
    if not single_path:
        ap.error("Provide a file (--path or positional), or use --input/--stdin for batch mode.")
    p = Path(single_path)
    if not p.exists():
        print(f"File not found: {p}", file=sys.stderr)
        sys.exit(2)
    res = process_file(
        path=p,
        ctype_cli=args.type,
        category_cli=args.category,
        force=args.force,
        hard_delete_previous=args.hard_delete_previous,
        skip_if_unchanged=not args.no_skip_if_unchanged,
        collection_name=args.collection,
        debug=args.debug,
        doc_id_key=args.doc_id_key,
        vault_root=args.vault_root,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

