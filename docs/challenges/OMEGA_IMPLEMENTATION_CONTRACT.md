# Ω∞ Challenge Integration

This repository is the executable companion for **VAIXLNS Ω∞ — Integrated Architecture Challenge**.

The canonical challenge definition lives in the VAIXLNS repository. This repository is responsible for turning the architecture into executable contracts, tests, golden scenarios, replay checks, verification paths, and recovery experiments.

## Required implementation loop

```
INTENT -> PLAN -> AUTHORIZE -> EXECUTE -> OBSERVE
       -> VERIFY -> PROVE -> RECORD -> REPLAY
       -> INJECT FAILURE -> RECOVER -> VERIFY -> RECORD
```

## Evidence rule

Implementation claims must be supported by repository/runtime evidence. Documentation alone is not proof.

## First implementation target

Build a deterministic golden execution with a deliberate controlled failure and a replayable recovery path.
