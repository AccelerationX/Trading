# Assistant Runtime

## Goal

The runtime layer stitches the assistant into one daily pipeline.

## Current Daily Flow

```text
optional Tushare source fetch
optional daily intake
-> account refresh
-> market regime
-> event/theme cards
-> capital behavior cards
-> assistant analysis bundle
-> candidate cards
-> trade plan cards
-> review memory
-> llm workpacks
-> llm execution plan
-> optional llm enrichment apply
-> daily pipeline report
```

## Runtime Command

Use:

`python scripts/run_assistant_pipeline.py --date YYYY-MM-DD`

If Tushare-backed inbox sources should be refreshed first:

`python scripts/run_assistant_pipeline.py --date YYYY-MM-DD --with-source-fetch`

If inbox files should be snapshotted first:

`python scripts/run_assistant_pipeline.py --date YYYY-MM-DD --with-intake`

## Runtime Behavior

The first version distinguishes between:

- mandatory layers
  - account
  - market regime
  - analysis bundle
  - candidate cards
  - trade plan cards
  - llm workpacks
  - llm execution plan
- optional layers
  - event/theme cards
  - capital behavior cards
  - llm enrichment apply

Optional layers may be skipped when the corresponding source files are absent.
The pipeline report records that explicitly.
