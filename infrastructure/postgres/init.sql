CREATE TABLE IF NOT EXISTS analyses (
  analysis_id TEXT PRIMARY KEY,
  image_sha256 CHAR(64) NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued','running','completed','partial','failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS engine_results (
  analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
  engine TEXT NOT NULL,
  status TEXT NOT NULL,
  findings JSONB NOT NULL DEFAULT '{}'::jsonb,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (analysis_id, engine)
);
