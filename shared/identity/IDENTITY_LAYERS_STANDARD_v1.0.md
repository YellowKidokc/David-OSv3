# Identity Layers Standard v1.0

**Authority:** David Lowe  
**Effective:** 2026-11-07  
**Canonical home:** `D:\GitHub\David-OSv3\shared\identity\`  
**Program contract:** `identity-envelope.v1.schema.json` and `layers.py`

## 1. Purpose

Every logical work receives one permanent root identity. Human codes, shortened UUIDs,
filenames, versions, API calls, analyses, Obsidian notes, representations and cross-domain
correspondences hang from that root. New identity schemes may be added without changing the
root or invalidating older records.

The standard fixes the invariant envelope, not a permanent count of identifier variables.
An object may currently carry one identifier layer or six. Consumers must read the ordered
`identifiers` and `relations` arrays rather than assuming fixed columns.

## 2. Invariant core

| Field | Rule |
|---|---|
| `root_uuid` | Immutable RFC 4122 UUID assigned once to the logical work |
| `short_uuid` | Display/search prefix derived from `root_uuid`; default 12 hex characters |
| `human_id` | Meaningful permanent registry ID such as `MEQU.03.TRUTH` when assigned |
| `identifiers[]` | Ordered, extensible alternate identity/name schemes |
| `relations[]` | DUAL Bridge relations to other UUID-addressed objects |
| `derivatives[]` | UUIDv5 children for versions, artifacts, API calls, analyses and renders |
| `assessments[]` | Versioned evidence/strength judgments; never part of immutable identity |

## 3. Short and long UUIDs

The long UUID is the complete 128-bit root in lowercase `8-4-4-4-12` form. The short UUID is
`u-` plus the first 12 hexadecimal characters in uppercase. If a registry collision ever occurs,
the display prefix is lengthened until unique. Short UUIDs are handles, not assignment authority.

Example:

```text
root_uuid:  4d59aecf-8b21-4f12-9c34-8a12e34c5678
short_uuid: u-4D59AECF8B21
human_id:   MIM.01.TRUTH
```

## 4. Extensible identifier layers

Each `identifiers[]` entry contains:

```text
order, scheme, value, expanded_value, authority, status, aliases, valid_from, valid_to
```

Suggested early layers are human canonical ID, series code, previous/legacy code, external ID,
symbolic identity and navigation/display name. The list is extensible; adding a scheme does not
alter the root UUID.

## 5. Derivative cascade

Every derivative is deterministic:

```text
derived_uuid = UUIDv5(root_uuid, "<category>:<canonical-key>")
```

Categories include `version`, `artifact`, `api`, `analysis`, `obsidian`, `sidecar`, `render` and
future registered categories. A derivative records its root UUID, derived UUID, role, derivation
key, source hash, creation time and producing program/version.

## 6. DUAL Bridge

DUAL preserves connections without collapsing two objects into one. Its visible label is:

```text
DUAL--<left-short>--<RELATION>--<right-short>
```

Core relations:

`SIMILAR_TO`, `STRUCTURALLY_ANALOGOUS_TO`, `SYMBOLIC_OF`, `REPRESENTS`, `DERIVED_FROM`,
`VERSION_OF`, `FORMAT_OF`, `SAME_WORK_AS`, `EXACT_CONTENT_AS`, `ISOMORPHIC_TO`.

`ISOMORPHIC_TO` requires a supplied bijective structure-preserving map and inverse. Resemblance,
shared symbolism or analogous organization use weaker relations. Every DUAL record carries
evidence, directionality, confidence, status and ruling provenance.

## 7. Strength is not identity

A paper's evidential, formal, theological or publication strength may change. Never encode that
mutable judgment into `root_uuid`, `short_uuid` or permanent `human_id`. Store it in
`assessments[]` with dimension, value, scale, method, evidence, evaluator, timestamp and version.
Names may display a current lifecycle/status code, but that display is derived and reversible.

## 8. Authority and mutation

1. The official registry assigns root UUIDs and human canonical IDs after David's approval.
2. Apps may propose but never silently assign authority-bearing identities.
3. Paths and filenames never determine identity.
4. Content hashes identify bytes/versions, not the timeless logical work.
5. Derived artifacts never become new roots unless an approved identity-displacement ruling says so.
6. All changes retain prior identifiers, lineage, receipts and reversibility.
7. Consumers must preserve unknown identifier/relation schemes rather than discard them.

## 9. Shared implementation

All Python apps import `shared.identity`. Non-Python apps implement
`identity-envelope.v1.schema.json`. No app maintains a private competing identity grammar.
