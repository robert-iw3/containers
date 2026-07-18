-- Demo data: the protected backend application database.
CREATE TABLE customers (
    id         serial PRIMARY KEY,
    name       text        NOT NULL,
    tier       text        NOT NULL DEFAULT 'standard',
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO customers (name, tier) VALUES
    ('Acme Corp',       'enterprise'),
    ('Globex',          'standard'),
    ('Initech',         'standard'),
    ('Umbrella Health', 'enterprise'),
    ('Stark Industries','enterprise');
