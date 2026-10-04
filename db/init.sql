-- Schemas, roles and tables (research R-02, R-03, R-06). Runs as the admin user of the database.
-- Local demo passwords only; no real secrets.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'actions_rw') THEN
        CREATE ROLE actions_rw LOGIN PASSWORD 'actions_pw';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_rw') THEN
        CREATE ROLE agent_rw LOGIN PASSWORD 'agent_pw';
    END IF;
END
$$;

REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- cases: owned by the Case Actions API ------------------------------------------------------------
CREATE SCHEMA cases AUTHORIZATION actions_rw;

CREATE TABLE cases.cases (
    id              uuid PRIMARY KEY,
    stage           text        NOT NULL,
    status          text        NOT NULL,
    version         integer     NOT NULL CHECK (version >= 1),
    policy_version  text        NOT NULL,
    state           jsonb       NOT NULL,
    created_at      timestamptz NOT NULL,
    updated_at      timestamptz NOT NULL
);
CREATE INDEX cases_status_stage_idx ON cases.cases (status, stage);

CREATE TABLE cases.escalations (
    id               uuid PRIMARY KEY,
    case_id          uuid        NOT NULL REFERENCES cases.cases (id),
    reason           text        NOT NULL,
    evidence         jsonb       NOT NULL,
    summary          text        NOT NULL,
    suggested_action text        NOT NULL,
    agent_note       text,
    status           text        NOT NULL CHECK (status IN ('open', 'resolved')),
    resolution       jsonb,
    created_at       timestamptz NOT NULL,
    resolved_at      timestamptz
);
CREATE INDEX escalations_status_idx ON cases.escalations (status, created_at);

-- scope = case id, or 'global' for create_case (DECISIONS.md, 2026-10-04)
CREATE TABLE cases.idempotency_keys (
    scope           text        NOT NULL,
    idempotency_key text        NOT NULL,
    tool            text        NOT NULL,
    request_hash    text        NOT NULL,
    http_status     integer     NOT NULL,
    response        jsonb       NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, idempotency_key)
);

ALTER TABLE cases.cases OWNER TO actions_rw;
ALTER TABLE cases.escalations OWNER TO actions_rw;
ALTER TABLE cases.idempotency_keys OWNER TO actions_rw;

-- audit: owned by the admin; actions_rw may only INSERT and SELECT ---------------------------------
CREATE SCHEMA audit;
GRANT USAGE ON SCHEMA audit TO actions_rw;

CREATE TABLE audit.audit_log (
    id                 bigserial PRIMARY KEY,
    case_id            uuid,
    at                 timestamptz NOT NULL DEFAULT now(),
    actor              text        NOT NULL,
    on_behalf_of       text,
    tool               text        NOT NULL,
    stage_before       text,
    status_before      text,
    stage_after        text,
    status_after       text,
    idempotency_key    text        NOT NULL,
    expected_version   integer,
    case_version_after integer,
    outcome            text        NOT NULL CHECK (outcome IN ('accepted', 'rejected')),
    rejection_code     text,
    input              jsonb       NOT NULL DEFAULT '{}'::jsonb,
    result             jsonb       NOT NULL DEFAULT '{}'::jsonb,
    events             jsonb       NOT NULL DEFAULT '[]'::jsonb,
    policy_version     text
);
CREATE INDEX audit_log_case_idx ON audit.audit_log (case_id, id);

CREATE FUNCTION audit.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit.audit_log is append-only (% rejected)', TG_OP;
END
$$;

CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit.audit_log
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();

CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit.audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit.reject_mutation();

GRANT SELECT, INSERT ON audit.audit_log TO actions_rw;
GRANT USAGE ON SEQUENCE audit.audit_log_id_seq TO actions_rw;

-- agent: owned by the agent (LangGraph checkpointer + channel idempotency) --------------------------
CREATE SCHEMA agent AUTHORIZATION agent_rw;

CREATE TABLE agent.processed_messages (
    case_id         uuid        NOT NULL,
    idempotency_key text        NOT NULL,
    response        jsonb       NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (case_id, idempotency_key)
);
ALTER TABLE agent.processed_messages OWNER TO agent_rw;
