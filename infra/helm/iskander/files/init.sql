-- Iskander database initialisation
-- Run once on first PostgreSQL start via the initdb ConfigMap.
-- Idempotent: uses IF NOT EXISTS throughout.
--
-- Each service gets its own database and a dedicated role with minimal
-- privileges. The shared 'iskander' superuser is used only for admin tasks.

-- ---------------------------------------------------------------------------
-- Authentik — SSO identity provider
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authentik') THEN
    CREATE ROLE authentik WITH LOGIN PASSWORD 'AUTHENTIK_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE authentik OWNER authentik;
GRANT ALL PRIVILEGES ON DATABASE authentik TO authentik;

-- ---------------------------------------------------------------------------
-- Loomio — governance and decision-making
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'loomio') THEN
    CREATE ROLE loomio WITH LOGIN PASSWORD 'LOOMIO_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE loomio OWNER loomio;
GRANT ALL PRIVILEGES ON DATABASE loomio TO loomio;

-- ---------------------------------------------------------------------------
-- Mattermost — real-time chat
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mattermost') THEN
    CREATE ROLE mattermost WITH LOGIN PASSWORD 'MATTERMOST_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE mattermost OWNER mattermost;
GRANT ALL PRIVILEGES ON DATABASE mattermost TO mattermost;

-- ---------------------------------------------------------------------------
-- Nextcloud — files, calendar, contacts
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nextcloud') THEN
    CREATE ROLE nextcloud WITH LOGIN PASSWORD 'NEXTCLOUD_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE nextcloud OWNER nextcloud;
GRANT ALL PRIVILEGES ON DATABASE nextcloud TO nextcloud;

-- ---------------------------------------------------------------------------
-- Decision recorder — IPFS bridge + audit log
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'decision_recorder') THEN
    CREATE ROLE decision_recorder WITH LOGIN PASSWORD 'DECISION_RECORDER_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE decision_recorder OWNER decision_recorder;
GRANT ALL PRIVILEGES ON DATABASE decision_recorder TO decision_recorder;

-- ---------------------------------------------------------------------------
-- Glass Box — agent action audit trail
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'glass_box') THEN
    CREATE ROLE glass_box WITH LOGIN PASSWORD 'GLASS_BOX_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE glass_box OWNER glass_box;
GRANT ALL PRIVILEGES ON DATABASE glass_box TO glass_box;

-- ---------------------------------------------------------------------------
-- OpenClaw — agent state and memory
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openclaw') THEN
    CREATE ROLE openclaw WITH LOGIN PASSWORD 'OPENCLAW_DB_PASSWORD_PLACEHOLDER';
  END IF;
END $$;

CREATE DATABASE openclaw OWNER openclaw;
GRANT ALL PRIVILEGES ON DATABASE openclaw TO openclaw;
