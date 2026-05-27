CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  CREATE TYPE job_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
EXCEPTION WHEN duplicate_object THEN
  NULL;
END$$;

DO $$
BEGIN
  CREATE TYPE job_stage AS ENUM (
    'QUEUED',
    'DOWNLOADING',
    'CONVERTING',
    'DIARIZATION',
    'TRANSCRIBING',
    'FINALIZING'
  );
EXCEPTION WHEN duplicate_object THEN
  NULL;
END$$;

CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  api_key TEXT UNIQUE NOT NULL,
  label TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  usage_count INT NOT NULL DEFAULT 0,
  quota INT,
  last_used_at TIMESTAMPTZ,
  tokens FLOAT NOT NULL DEFAULT 60.0,
  last_refill TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transcription_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_type TEXT NOT NULL CHECK (source_type IN ('UPLOAD', 'URL')),
  source_url TEXT,
  filename TEXT,
  model TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
  status job_status NOT NULL DEFAULT 'PENDING',
  stage job_stage NOT NULL DEFAULT 'QUEUED',
  error_code TEXT,
  error_message TEXT,
  suggested_action TEXT,
  result JSONB,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  attempts INT NOT NULL DEFAULT 0,
  callback_url TEXT,
  api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_transcription_jobs_status ON transcription_jobs(status);
CREATE INDEX IF NOT EXISTS idx_transcription_jobs_status_stage ON transcription_jobs(status, stage);
CREATE INDEX IF NOT EXISTS idx_transcription_jobs_created_at ON transcription_jobs(created_at);
