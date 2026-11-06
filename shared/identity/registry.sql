-- Document Identity Standard v1.0 registry (SQLite). Append-only by design:
-- rows are never updated in place except documents.current_version / series.member_count.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS series (
  series_id        TEXT PRIMARY KEY CHECK (series_id GLOB '[A-Z][A-Z][A-Z]*' AND length(series_id) BETWEEN 3 AND 5),
  canonical_title  TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'active',
  member_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
  document_id      TEXT PRIMARY KEY,                 -- SERIES.POSITION.SLUG
  canonical_title  TEXT,
  series_id        TEXT NOT NULL REFERENCES series(series_id),
  position         INTEGER NOT NULL CHECK (position BETWEEN 0 AND 99),
  slug             TEXT NOT NULL,
  current_version  INTEGER,
  status           TEXT NOT NULL DEFAULT 'assigned', -- assigned | displaced | planned
  note             TEXT,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (series_id, position)
);

CREATE TABLE IF NOT EXISTS versions (
  version_id       TEXT PRIMARY KEY,                 -- UUIDv7
  document_id      TEXT NOT NULL REFERENCES documents(document_id),
  version_number   INTEGER NOT NULL,
  content_sha256   TEXT NOT NULL,
  created_at       TIMESTAMP NOT NULL,
  supersedes       TEXT REFERENCES versions(version_id),
  revision_status  TEXT,
  UNIQUE (document_id, version_number)
);

CREATE TABLE IF NOT EXISTS runs (
  run_id           TEXT PRIMARY KEY,                 -- RUN-<timestamp>
  pipeline_id      TEXT NOT NULL,
  pipeline_version TEXT,
  started_at       TIMESTAMP,
  completed_at     TIMESTAMP,
  status           TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id      TEXT PRIMARY KEY,                 -- UUIDv7; never reused, never overwritten
  document_id      TEXT NOT NULL REFERENCES documents(document_id),
  version_id       TEXT REFERENCES versions(version_id),
  artifact_role    TEXT NOT NULL,
  artifact_version INTEGER NOT NULL DEFAULT 1,
  run_id           TEXT REFERENCES runs(run_id),
  content_sha256   TEXT NOT NULL,
  file_path        TEXT,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (document_id, version_id, artifact_role, artifact_version)
);

CREATE TABLE IF NOT EXISTS relations (
  source_id        TEXT NOT NULL REFERENCES documents(document_id),
  relationship     TEXT NOT NULL,                    -- SUPERSEDED_BY, DERIVED_FROM, SOURCE_NARRATIVE_FOR, INTERPRETS, ILLUSTRATES ...
  target_id        TEXT NOT NULL REFERENCES documents(document_id),
  PRIMARY KEY (source_id, relationship, target_id)
);

-- Safety rule 5: IDs are applied to existing files only through this ledger.
CREATE TABLE IF NOT EXISTS approvals (
  approval_id      TEXT PRIMARY KEY,
  document_id      TEXT NOT NULL REFERENCES documents(document_id),
  action           TEXT NOT NULL,                    -- assign_id | apply_sidecar | move | admit
  approved_by      TEXT NOT NULL CHECK (approved_by = 'David Lowe'),
  approved_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  evidence         TEXT
);

-- Safety rule 4: a displaced document_id can never be re-pointed or reused.
CREATE TRIGGER IF NOT EXISTS no_reuse_displaced
BEFORE UPDATE OF series_id, position, slug ON documents
WHEN OLD.status = 'displaced'
BEGIN SELECT RAISE(ABORT, 'displaced document_id cannot be reused'); END;

-- Safety rule 3: identity fields are permanent.
CREATE TRIGGER IF NOT EXISTS id_fields_permanent
BEFORE UPDATE OF document_id, series_id, position, slug ON documents
BEGIN SELECT RAISE(ABORT, 'document_id is permanent'); END;

-- Safety rule 2: artifacts are never overwritten.
CREATE TRIGGER IF NOT EXISTS artifacts_append_only
BEFORE UPDATE ON artifacts
BEGIN SELECT RAISE(ABORT, 'artifacts are append-only; create a new artifact'); END;
