# Information-First Optimization

## Why this phase exists

The current system is usable, but the recommendation path still leans too heavily on technical triggers.

For A-share trading, that is not enough. Major returns are often driven by:

- policy shifts
- official company events
- sector theme expansion
- crowding and emotional regime changes
- capital confirmation after the information shock

So the next optimization phase must shift the system from:

- `technical selection + information explanation`

to:

- `information prioritization + sentiment framing + technical confirmation`

## Target behavior

The system should answer in this order:

1. What happened from yesterday close to today preopen?
2. Which of those events actually matter for A-share trading today?
3. Which sectors or themes are likely to become the main battlefield?
4. Which stocks are direct beneficiaries, secondary beneficiaries, or only noise followers?
5. Which of those names are technically tradable for this account?

Technical analysis remains necessary, but its role becomes:

- timing confirmation
- risk filtering
- execution discipline

not primary idea generation.

## Optimization priorities

### 1. Sentiment Layer

Add a dedicated A-share sentiment layer, separate from simple market breadth.

It should judge:

- whether the market is in expansion, rotation, contraction, or failed-speculation mode
- whether leaders are stable or fragile
- whether the environment favors event continuation, trend following, or only defensive observation

This layer should heavily affect which setups are allowed to become actionable.

### 2. Event-First Candidate Logic

Candidate ranking should be biased toward names with real information edge:

- official company events
- policy/theme mapping
- overnight text signals with clear beneficiaries
- capital confirmation after the event

Module-only names should still exist, but they should be treated as lower-conviction technical ideas unless information support appears.

### 3. Theme Board Instead of Flat Stock List

The system should increasingly think in terms of:

- main theme
- leader
- secondary names
- low-quality followers

instead of generating a flat set of unrelated stock ideas.

### 4. Source Hierarchy

The source hierarchy should remain strict:

- `A`: official hard information
- `B`: useful but secondary fast information
- `C`: weak or rumor-like information

Only A-class information should be able to directly anchor recommendation logic.

## Implementation sequence

### Phase A

- add `sentiment_cycle`, `leader_stability`, `event_driven_bias`
- expose these in the market regime output and preopen summary

### Phase B

- add `information_edge_score`
- shift candidate scoring toward event/theme/text support
- cap module-only ideas unless they gain information support

### Phase C

- build a theme-first recommendation board
- separate direct beneficiaries from weak followers

### Phase D

- add more official and fast information sources
- improve beneficiary mapping quality
- evaluate information-driven vs technical-driven recommendations separately

## Success criteria

This phase is successful when:

- top-ranked names are usually explainable by clear event/theme logic
- module-only technical names are no longer overrepresented
- the preopen summary reads like a trader's research brief instead of a technical watchlist
