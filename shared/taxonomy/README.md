# Vault taxonomy (status: PROPOSED, 2026-11-06)

The full proposed tree was pasted in chat on 2026-11-06 and is the reference for routing.
**It doesn't authorize creating or moving any folders.** Apps may only *propose* a primary home
(a future `routing-proposal.v1` record). A human reviews every move.

Top level:
| Code | Home | Holds |
|---|---|---|
| 00 | ORIENTATION_AND_INBOX | inboxes, orientation, governing principles, navigation |
| 10 | ACTIVE_EFFORTS | work being done now (projects, drafts, plans, handoffs) |
| 20 | KNOWLEDGE_ATLAS | concepts, axioms, equations, bridges, domains, Master Equation |
| 30 | SOURCES_AND_RESEARCH | outside evidence and research activity |
| 40 | CANONIZATION | 01_CANDIDATE → 02_CANONIZATION_LIBRARY → 03_CANON_LIBRARY (never skip a stage) |
| 50 | PRODUCTION_AND_PUBLICATION | finished work for readers |
| 60 | MEDIA_AND_DATA | media and structured technical assets |
| 70 | PEOPLE_AND_WORLDVIEWS | people, traditions, rival frameworks |
| 80 | SYSTEM_TOOLS_AND_AUTOMATION | software and operations (David-OS, FIS, action library) |
| 90 | ARCHIVE_AND_RECOVERY | preserved history that's no longer active |
| 99 | REVIEW_AND_QUARANTINE | unresolved or unsafe material, and proposals waiting on a decision |

Placement rule: **one physical home per file, many metadata classifications** (subject, domains,
functions, lifecycle, canon_status, confidence). Never copy a file to place it in more than one category.

TODO: store the full tree as `vault_taxonomy.v1.yaml` once it's approved.
