# Nabla — address/vector component of the Document Classifier

The overall tool is named **Document Classifier**. Nabla retains its name and
runs underneath it for document addresses and vectors. This naming does not
change the protocol, stored coordinates or the separate χ/Master Equation feed.

Parallel classification vocabulary to the tag taxonomy (Part A). Where the
taxonomy answers "what tags," Nabla gives each document a compact **address**
an AI can scan to decide what to open *before* opening it.

## What's here
- `nabla_atlas.py` — the deterministic core (audience validation added for Stage 1). Does NOT make
  semantic judgments; it validates, encodes, decodes, and computes the pairing
  signature. The vector (what the document IS) is supplied by a human or model
  and carries provenance.
- `documents\` — drop test specimens here.

## The address
```
DOMAIN/ENTITY/STATE/AUDIENCE/USE/RISK :: <10-var vector> :: <pairing signature>
```
Ten variables G M E S T K R Q F C, each scored **0 or 3** (absent / dominant)
for the stored address. Signature is computed by the tool — never hand-written.

## Commands
```
python nabla_atlas.py address  input.json    # full record from a vector
python nabla_atlas.py validate input.json    # just check validity
python nabla_atlas.py decode  "<address>"    # reverse: fields + dominant/absent + hash_valid
python nabla_atlas.py chi     factors.json   # coherence profile (NOT a truth score)
```

## Proven portable (2026-11-01)
BOOK_06A (Sign Theorem) classified by Fable → address handed to GPT cold →
GPT's independent decode and re-classification returned **zero coordinate
differences** (§9 exact match). Two models round-tripped one document through
a 16-char address and arrived at the same understanding. The retrieval layer
works across minds.

Worked example address:
```
THEOPHYSICS/SIGN_THEOREM/W/AI_RESEARCH/T/R1 :: G3M3E0S3T0K3R3Q0F3C3 :: [C·Q][G·T][K·E][M·S][R·F]
```

## Audience validation (Stage 1)
`Filing.validate()` now checks `audience` against `AUDIENCES`, alongside domain,
state, use and risk. The four explicitly documented audiences are `SELF`, `TEAM`,
`PUBLIC`, `AI_RESEARCH`; other strings are refused. Additional audiences require
an explicit vocabulary update rather than accepting arbitrary strings.

## Honesty firewall (keep, don't soften)
- A valid signature proves the ENCODING is internally consistent. It does NOT
  prove the classification is accurate, nor that the document's claims are true.
- `E` scores DISORDER OF THE ARTIFACT, not its subject. A clear, complete paper
  about brokenness is E0 — well-formed. Do not conflate topic with disorder.
- Store confidence separately. A classifier's uncertainty never makes a
  document disordered.
- The 0/3 stored scores and any 1–3 working intensity ratings are DIFFERENT
  systems — never silently mix them; record which protocol produced a score.

## Integration target
Nabla fields (address, vector, signature, confidence, decode sentence) become
columns in the same per-document record the Stage-1 registry stores, and the
FIS/HTML display is generated from that one record — visible name and JSON from
a single source of truth (spec §7). Classify once per source version; reuse
across FIS, SQLite, search, exports; reclassify only when the source changes.
