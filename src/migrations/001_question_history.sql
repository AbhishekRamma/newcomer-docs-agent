-- Per-user question history. user_sub is the `sub` claim of the caller's access token.
CREATE TABLE IF NOT EXISTS question_history (
    id          BIGSERIAL PRIMARY KEY,
    user_sub    TEXT        NOT NULL,
    question    TEXT        NOT NULL,
    answer_json JSONB       NOT NULL,
    route       TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS question_history_user_newest
    ON question_history (user_sub, created_at DESC, id DESC);
