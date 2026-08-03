# Phase 3 — Personal Playstyle Engine

## Purpose

The Personal Playstyle Engine (PPE) converts reviewed raid evidence into an explainable, context-specific player profile. It is not a hidden rating system and does not treat a single death, survival, or successful raid as proof of a permanent trait.

The PPE answers four separate questions:

1. What patterns are currently supported by recorded evidence?
2. In which contexts do those patterns appear or change?
3. How confident should the system be?
4. Should the player adapt around a limitation for progression, deliberately train it, or gather more evidence?

## Core safeguards

- Raw review data remains separate from profile interpretation.
- Only finalized raid reviews are automatically converted into PPE evidence.
- Free-text narratives are preserved but are not automatically interpreted as skill evidence.
- Outcome-only evidence receives deliberately low weight.
- Multiple observations from one raid are capped so one unusual raid cannot dominate a dimension.
- Older evidence decays gradually rather than disappearing abruptly.
- Contradictory evidence lowers confidence and may produce a context-dependent conclusion.
- Adaptation guidance is separate from optional deliberate training.
- Every snapshot stores its evidence fingerprint, version, estimates, and an audit record of changes.

## Profile dimensions

The initial registry contains dimensions across five categories.

### Combat and mechanics

- Prepared engagement effectiveness
- Reactive close-range effectiveness
- First-shot execution
- Target tracking
- Recoil recovery

### Positioning

- Angle discipline
- Cover utilization
- Repositioning

### Information

- Route prediction
- Audio interpretation
- Map timing
- Information patience
- Interception prediction

### Decision making

- Fight selection
- Disengagement
- Objective discipline
- Risk management
- Contact conversion
- Execution decisiveness
- Overcommitment control

### Mental stability

- Pressure stability
- Gear-risk stability

The registry is versioned in source code. Each definition includes:

- a stable key;
- a human-readable description;
- positive and negative interpretations;
- relevant context fields;
- evidence half-life;
- minimum evidence expectations;
- adaptation guidance;
- optional training guidance.

## Evidence model

A PPE evidence record contains:

- source type;
- source reference;
- raid and encounter identifiers when applicable;
- observation time;
- reliability;
- structured context;
- one or more dimension impacts;
- rationale for every impact.

Each impact contains:

- dimension key;
- directional value from `-1.0` to `+1.0`;
- strength;
- confidence;
- evidence role;
- explicit rationale.

Supported evidence roles are performance, decision, preference, constraint, and outcome. This prevents a preference statement from being silently treated as a mechanical ability measurement.

## Automatic extraction from raid reviews

The deterministic extractor uses only explicit structured fields. Examples include:

- a mutually detected close-range loss can affect reactive close-range effectiveness;
- firing first and losing can affect first-shot execution;
- a same-angle re-peek affects angle discipline;
- an explicit reposition affects repositioning;
- choosing not to disengage when disengagement was available can affect overcommitment control;
- explicit objective completion affects objective discipline;
- survival or death alone affects risk management only slightly.

The extractor does **not** infer PvP weakness from a raid with no PMC contact. It does not parse narrative prose for psychological conclusions, and it does not interpret raw accuracy without a validated context model.

## Weighting and confidence

For each observation, the initial effective weight is:

```text
source multiplier
× evidence reliability
× impact strength
× impact confidence
× recency factor
```

The recency factor uses exponential half-life decay. The half-life is defined per dimension.

Evidence is then capped by raid and dimension. Repeating many impacts from one raid cannot equal the independence of evidence collected across many raids.

A neutral prior pulls low-evidence scores toward zero. Confidence rises with effective weight, but it is reduced by contradiction. Equal positive and negative evidence therefore produces a low-direction, lower-confidence estimate rather than an arbitrary winner.

## Context segmentation

Each dimension defines the context fields that matter to it. Depending on the dimension, the PPE may create estimates for:

- map;
- engagement range;
- detection order;
- objective priority;
- group size;
- position state;
- weapon or loadout family;
- opponent type;
- combinations of the relevant fields.

Global estimates and contextual estimates coexist. A weak Factory close-range result does not automatically overwrite evidence from medium-range prepared engagements on Interchange.

## Profile snapshots and audit history

Every changed evidence corpus creates a new immutable profile snapshot. A snapshot includes:

- version;
- generation time;
- evidence fingerprint;
- evidence count;
- global and contextual estimates;
- confidence and effective weight;
- independent raid count;
- contradiction ratio;
- supporting evidence references;
- strengths, constraints, uncertain dimensions, and caveats.

The audit record stores the trigger, evidence identifiers, previous snapshot, and dimensions whose score or confidence changed meaningfully.

Rebuilding with an unchanged evidence fingerprint returns the current snapshot rather than manufacturing another history entry. A force rebuild may be used when an explicit historical checkpoint is desired.

## Adaptation versus training

A limitation does not become a mandatory training assignment.

**Adaptation guidance** is intended to support current progression. It may recommend creating prepared engagements, preserving disengagement routes, using predictable budget tiers, or avoiding equal-information close-range entries.

**Training guidance** is an optional controlled experiment. It should isolate one variable in Arena, offline practice, or low-cost raids without making progression depend on the weakest skill.

## Local outputs

Current global outputs are written under:

```text
<data_root>/ppe/
├── profile-current.json
├── profile-report.json
├── profile-report.md
└── history/
    └── profile-v####.json
```

Each finalized raid package may also receive:

```text
analysis/ppe-evidence.json
analysis/ppe-profile-impact.json
```

These files record the profile inputs and touched dimensions. They explicitly avoid claiming that one raid establishes a trait.

## Browser and API

Start the local application:

```powershell
tarkov-agent serve --config config.toml
```

Open:

```text
http://127.0.0.1:8765/ppe
```

The dashboard displays:

- global signals;
- confidence and evidence counts;
- contextual estimates;
- adaptation guidance;
- deliberate training options;
- profile history;
- recent evidence;
- an explicit manual-evidence form.

Key API routes include:

```text
GET  /api/ppe/dimensions
GET  /api/ppe/profile
GET  /api/ppe/profile/history
GET  /api/ppe/profile/audit
GET  /api/ppe/evidence
GET  /api/ppe/raids/{raid_id}/evidence
GET  /api/ppe/report
POST /api/ppe/evidence/manual
POST /api/ppe/rebuild
GET  /api/ppe/export/markdown
GET  /api/ppe/export/json
```

## CLI

Recalculate the profile from stored evidence:

```powershell
tarkov-agent ppe-rebuild --config config.toml
```

Create an explicit historical checkpoint even when the evidence fingerprint has not changed:

```powershell
tarkov-agent ppe-rebuild --config config.toml --force
```

## Exit condition

Phase 3 is complete when repeated finalized raid evidence produces versioned, explainable, context-specific profile updates; contradictory evidence lowers certainty; one raid cannot dominate the profile; and adaptation remains distinct from optional training.
