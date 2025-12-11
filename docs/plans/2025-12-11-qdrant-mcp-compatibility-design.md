# Qdrant MCP Compatibility Design

**Date:** 2025-12-11
**Goal:** Enable `/daily-briefing-v2` to perform semantic search via the MCP `qdrant-find` tool

## Problem Statement

The `/daily-briefing-v2` command needs to search the `personal_assistant` Qdrant collection using the MCP server's `qdrant-find` tool. Currently, there are two incompatibilities:

1. **Vector naming mismatch**: The collection uses unnamed vectors, but the MCP server expects named vectors (passes `using=vector_name`)
2. **Payload structure mismatch**: The collection payload lacks a `document` field; the MCP server expects `payload["document"]` to contain searchable text content

## Current State

- **Collection**: `personal_assistant` with 1,868 points
- **Vector config**: Unnamed vectors (768 dimensions, Cosine distance)
- **Payload fields**: `type`, `category`, `title`, `path`, `doc_id`, `doc_version`, `chunk_idx`, `chunk_chars`, `people`, `tags`, `is_active`, `ingested_at`, `source_mtime`, `content_sha`
- **Missing**: Chunk text content is not stored (only embedded)

## Design

### Changes to `embed_to_qdrant.py`

1. **Add `document` field to payload** containing the chunk text
   - Field name `document` aligns with MCP server expectations
   - Stores full chunk text (~1,200 chars per chunk based on CHUNK_SIZE)

2. **Use named vectors** instead of unnamed
   - Change from: `PointStruct(id=pid, vector=vec, payload=payload)`
   - Change to: `PointStruct(id=pid, vector={"text_embedding_004": vec}, payload=payload)`
   - Vector name matches `EMBED_MODEL` with formatting (dashes to underscores)

### Changes to Qdrant Collection

- **Delete existing collection**: Required because vector config (named vs unnamed) cannot be changed in place
- **Recreate with named vectors**: Collection will be auto-created on first upsert with new config
- **Re-ingest all documents**: Run batch ingestion with `--force` flag

### Changes to MCP Server

- **None required**: The MCP server already expects:
  - Named vectors (uses `using=vector_name`)
  - `document` field in payload

## Implementation Steps

1. Modify `embed_to_qdrant.py`:
   - Add `"document": chunk` to payload dict (around line 625)
   - Change `PointStruct` to use named vector dict (line 641)
   - Update `ensure_collection()` to create named vector config

2. Delete existing collection:
   ```bash
   curl -X DELETE "http://localhost:6333/collections/personal_assistant"
   ```

3. Re-ingest all documents:
   ```bash
   cd /Users/eriknewby/scripts/ai_scripts
   ./.venv/bin/python embed_to_qdrant.py \
     --input "/Users/eriknewby/Obsidian/RedHat+/Process/meetings" \
     --input "/Users/eriknewby/Obsidian/RedHat+/Process/one-on-one" \
     --input "/Users/eriknewby/Obsidian/RedHat+/Meetings" \
     --recursive --ext md \
     --collection personal_assistant \
     --vault-root "/Users/eriknewby/Obsidian" \
     --force
   ```

4. Verify:
   - Test `qdrant-find` tool with a sample query
   - Run `/daily-briefing-v2` command

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss during re-ingestion | Source files in Obsidian vault are unchanged; can always re-ingest |
| Embedding API costs | One-time cost; ~1,868 chunks to re-embed |
| MCP server needs restart | Restart Claude Code after changes to pick up new config |

## Success Criteria

- [ ] `qdrant-find` returns results with `document` field containing chunk text
- [ ] `/daily-briefing-v2` successfully performs semantic search
- [ ] Search results include metadata (`people`, `tags`, `path`, etc.)
