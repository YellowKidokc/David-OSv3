-- TOP AI FIS initial SQLite schema.
-- This is the shared cache/history layer for API calls, clipboard, file events,
-- scans, labels, actions, node status, and preference learning.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'watcher',
  base_url TEXT,
  machine_name TEXT,
  status TEXT NOT NULL DEFAULT 'unknown',
  last_seen_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  source_node_id TEXT,
  target TEXT,
  route TEXT NOT NULL,
  method TEXT NOT NULL,
  status_code INTEGER,
  request_summary TEXT,
  response_summary TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clipboard_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_node_id TEXT,
  source_app TEXT,
  content_type TEXT NOT NULL DEFAULT 'text/plain',
  content TEXT,
  content_hash TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  priority INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_buckets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bucket_id TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  path TEXT NOT NULL,
  owner TEXT NOT NULL DEFAULT 'operator',
  visibility TEXT NOT NULL DEFAULT 'private',
  allowed_agents TEXT NOT NULL DEFAULT '[]',
  vector_namespace TEXT,
  requires_approval_to_share INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL UNIQUE,
  bucket_id TEXT NOT NULL,
  path TEXT,
  source TEXT,
  title TEXT,
  content_type TEXT NOT NULL DEFAULT 'text/markdown',
  content_hash TEXT,
  tags TEXT NOT NULL DEFAULT '[]',
  visibility TEXT NOT NULL DEFAULT 'bucket',
  importance INTEGER NOT NULL DEFAULT 0,
  indexed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(bucket_id) REFERENCES memory_buckets(bucket_id)
);

CREATE TABLE IF NOT EXISTS knowledge_banks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bank_id TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT,
  default_bucket_id TEXT,
  visibility TEXT NOT NULL DEFAULT 'project',
  allowed_agents TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_bank_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bank_id TEXT NOT NULL,
  memory_id TEXT,
  file_record_id INTEGER,
  source_path TEXT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(bank_id) REFERENCES knowledge_banks(bank_id),
  FOREIGN KEY(memory_id) REFERENCES memory_items(memory_id),
  FOREIGN KEY(file_record_id) REFERENCES file_records(id)
);

CREATE TABLE IF NOT EXISTS file_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT,
  source_node_id TEXT,
  event_type TEXT NOT NULL,
  path TEXT NOT NULL,
  old_path TEXT,
  extension TEXT,
  size_bytes INTEGER,
  modified_at TEXT,
  file_hash TEXT,
  folder_profile TEXT,
  status TEXT NOT NULL DEFAULT 'received',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  extension TEXT,
  size_bytes INTEGER,
  file_hash TEXT,
  title TEXT,
  category TEXT,
  state TEXT NOT NULL DEFAULT 'unknown',
  protected INTEGER NOT NULL DEFAULT 0,
  last_seen_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS folder_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_node_id TEXT,
  target_path TEXT NOT NULL,
  grade TEXT,
  score INTEGER,
  total_files INTEGER,
  total_dirs INTEGER,
  report_json TEXT NOT NULL,
  report_html_path TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS text_chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  bucket_id TEXT,
  bank_id TEXT,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT,
  token_count INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vector_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  vector_id TEXT NOT NULL UNIQUE,
  chunk_id TEXT NOT NULL,
  namespace TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  dimensions INTEGER,
  vector_ref TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(chunk_id) REFERENCES text_chunks(chunk_id)
);

CREATE TABLE IF NOT EXISTS file_labels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_record_id INTEGER,
  path TEXT NOT NULL,
  label_type TEXT NOT NULL,
  label_value TEXT NOT NULL,
  confidence REAL,
  source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(file_record_id) REFERENCES file_records(id)
);

CREATE TABLE IF NOT EXISTS rename_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  original_name TEXT NOT NULL,
  suggested_name TEXT NOT NULL,
  style TEXT NOT NULL,
  confidence REAL,
  accepted INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  proposal_id TEXT,
  action_type TEXT NOT NULL,
  path TEXT NOT NULL,
  target_path TEXT,
  reason TEXT,
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'pending',
  requires_approval INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_at TEXT
);

CREATE TABLE IF NOT EXISTS action_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  proposal_id TEXT,
  action_type TEXT NOT NULL,
  path TEXT NOT NULL,
  target_path TEXT,
  result TEXT NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS command_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL UNIQUE,
  source_node_id TEXT,
  command TEXT NOT NULL,
  working_dir TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  requires_approval INTEGER NOT NULL DEFAULT 1,
  approved_by TEXT,
  stdout TEXT,
  stderr TEXT,
  exit_code INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS dispatch_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dispatch_id TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  target_agent TEXT,
  target_route TEXT,
  message TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'queued',
  response_summary TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_tools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool_id TEXT NOT NULL UNIQUE,
  server_name TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  description TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  call_id TEXT NOT NULL UNIQUE,
  tool_id TEXT,
  source_agent TEXT,
  request_json TEXT NOT NULL,
  response_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(tool_id) REFERENCES mcp_tools(tool_id)
);

CREATE TABLE IF NOT EXISTS preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  weight REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scope, key)
);

CREATE TABLE IF NOT EXISTS transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_state TEXT NOT NULL,
  action TEXT NOT NULL,
  to_state TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(from_state, action, to_state)
);
