# Historical generated tagger indexes

These four CSVs (including the two largest) are losslessly archived as deterministic gzip files.
They are not inputs to the live tagger or wheel package. `manifest.json` records original
paths, sizes and SHA-256 hashes, plus compressed hashes. All four were decompressed and
compared byte-for-byte before removing the generated originals from the working tree.

Restore one with `python -m gzip -d filename.csv.gz` on a copy, then compare its SHA-256
with the manifest. Restore to its recorded source path only if needed for historical analysis.
Older Git commits still contain the original blobs; this change does not rewrite shared history.
