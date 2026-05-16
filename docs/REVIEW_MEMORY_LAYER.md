# Review Memory Layer

## Goal

The review-memory layer turns manual trade-review notes into structured memory entries.

## Current Input

The first version reads markdown notes from:

- `workspace/reviews/**/*.md`

These notes should follow the existing trade-review template.

## Current Output

The layer generates `review_memory_entries` with:

- stock code
- action
- outcome tag
- setup tags
- lesson summary
- actionable rule
- retrieval keys

## Why This Matters

This is the first step toward letting the assistant learn from your own trading history without pretending to retrain a model.

The system will later be able to retrieve:

- similar historical situations
- what you did
- what worked
- what failed
- what rule should be reused or avoided
