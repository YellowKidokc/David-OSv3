# BFP-DG 3-Call Pipeline Run

Mode: `test`
Provider: `deepseek`
Model: `deepseek-chat`
Files processed: `1`
API calls per file: `4` (pills A, B, C, D)

Design rule: Classifications are outputs, not inputs.
Claim ledger: claims cataloged in A, graded in B, finalized in C.
Claim modes: test=True, draft=False, live=False

Orphan claims carry forward until connected or killed by a future run.
