# Text Signal Watch

## Goal

This layer ranks the day's text-heavy signals before they are passed to deeper interpretation.

It is designed to reduce noise from:

- exchange filings
- official market-news text
- policy documents
- catalyst calendars

## Output

The layer produces:

- `text_signal_watch_YYYY-MM-DD.json`
- `text_signal_watch_YYYY-MM-DD.md`

## Current Rule

Current ranking is still rule-based.

It combines:

- source trust tier
- source type
- explicit priority keywords
- stock specificity
- industry specificity

This makes the text queue smaller and more usable before any LLM is connected.
