# Capital Behavior Layer

## Goal

The capital-behavior layer converts raw capital-flow related inputs into one unified object:

- `capital_behavior_card`

This gives the assistant a reusable capital-confirmation layer before LLM is introduced.

## Current Sources

The first implementation reads three source families:

- `dragon_tiger_board`
- `northbound_and_margin_flow`
- `block_trade_and_abnormal_volume`

## Current Output

Each card carries:

- stock code
- signal type
- participation strength
- consistency score
- suspected style
- support or distribution
- warning flags

## Design Note

The current version is deliberately heuristic and source-tolerant.

That means:

- field names are matched loosely
- JSON and CSV are both acceptable
- the first goal is pipeline stability, not perfect interpretation

Later, LLM will improve:

- seat interpretation
- sustainability judgment
- crowding risk explanation
- confirmation versus distribution analysis
