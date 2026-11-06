# Contracts

Pipeline: inventory → fingerprint → classify → rename-proposal → human review.

Every record carries source_path, sha256, producer, schema_version, created_at, status.
Breaking change = new file (`*.v2.schema.json`); v1 stays readable.
