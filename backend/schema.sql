CREATE TABLE users (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 email text UNIQUE NOT NULL, name text NOT NULL, password_hash text NOT NULL,
 role text NOT NULL CHECK(role IN ('admin','user','bi')), active boolean NOT NULL DEFAULT true,
 token_limit bigint NOT NULL DEFAULT 20000 CHECK(token_limit>=0),
 tokens_used bigint NOT NULL DEFAULT 0 CHECK(tokens_used>=0),
 tokens_reserved bigint NOT NULL DEFAULT 0 CHECK(tokens_reserved>=0),
 bi_scope bigint REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 csrf text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE categories (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 name text NOT NULL, kind text NOT NULL CHECK(kind IN ('income','expense')),
 active boolean NOT NULL DEFAULT true, UNIQUE(user_id,name,kind)
);
CREATE TABLE recurring (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 category_id bigint NOT NULL REFERENCES categories(id), title text NOT NULL,
 amount numeric(15,2) NOT NULL CHECK(amount>0), start_month date NOT NULL CHECK(EXTRACT(DAY FROM start_month)=1),
 active boolean NOT NULL DEFAULT true
);
CREATE TABLE obligations (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 category_id bigint NOT NULL REFERENCES categories(id), title text NOT NULL,
 planned numeric(15,2) NOT NULL CHECK(planned>0), due_date date NOT NULL,
 recurring_id bigint REFERENCES recurring(id), voided boolean NOT NULL DEFAULT false,
 UNIQUE(recurring_id,due_date)
);
CREATE TABLE payments (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, obligation_id bigint NOT NULL REFERENCES obligations(id),
 amount numeric(15,2) NOT NULL CHECK(amount>0), paid_on date NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE goals (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 name text NOT NULL, target numeric(15,2) NOT NULL CHECK(target>0), deadline date NOT NULL,
 active boolean NOT NULL DEFAULT true
);
CREATE TABLE savings (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, goal_id bigint NOT NULL REFERENCES goals(id),
 amount numeric(15,2) NOT NULL CHECK(amount<>0), moved_on date NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE knowledge (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, title text NOT NULL,
 body text NOT NULL, source text NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE INDEX knowledge_search ON knowledge USING gin(to_tsvector('spanish',title||' '||body));
CREATE TABLE services (
 id text PRIMARY KEY CHECK(id IN ('rag','budget','goals')), name text NOT NULL,
 enabled boolean NOT NULL DEFAULT true, model text NOT NULL DEFAULT 'openai/gpt-oss-120b',
 max_output integer NOT NULL DEFAULT 768 CHECK(max_output BETWEEN 128 AND 768),
 max_rounds integer NOT NULL DEFAULT 6 CHECK(max_rounds BETWEEN 2 AND 6),
 deleted_at timestamptz,
 CONSTRAINT services_deleted_disabled_check CHECK(deleted_at IS NULL OR NOT enabled)
);
CREATE TABLE conversations (
 id uuid PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id),
 service text NOT NULL REFERENCES services(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE requests (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id),
 user_id bigint NOT NULL REFERENCES users(id), service text NOT NULL REFERENCES services(id),
 prompt text NOT NULL, response text NOT NULL DEFAULT '', sources jsonb NOT NULL DEFAULT '[]',
 status text NOT NULL DEFAULT 'running' CHECK(status IN ('running','success','failed')),
 error_code text, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 pending_tokens bigint NOT NULL DEFAULT 0 CHECK(pending_tokens>=0),
 pending_day text, pending_minute text, pending_model text, pending_started timestamptz
);
CREATE INDEX request_filters ON requests(user_id,created_at,service);
CREATE TABLE provider_calls (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, request_id uuid NOT NULL REFERENCES requests(id),
 model text NOT NULL, input_tokens bigint NOT NULL CHECK(input_tokens>=0),
 output_tokens bigint NOT NULL CHECK(output_tokens>=0),
 usage_kind text NOT NULL CHECK(usage_kind IN ('provider','reserved_unknown','rejected')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE tool_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, request_id uuid NOT NULL REFERENCES requests(id),
 name text NOT NULL, arguments jsonb NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE budgets (
 period text PRIMARY KEY, used bigint NOT NULL DEFAULT 0, reserved bigint NOT NULL DEFAULT 0
);
CREATE TABLE audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor_id bigint NOT NULL REFERENCES users(id),
 action text NOT NULL, entity text NOT NULL, entity_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
