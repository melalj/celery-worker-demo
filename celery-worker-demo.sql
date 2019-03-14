CREATE TABLE domains (
    domain text PRIMARY KEY,
    alexa_rank int,
    updated_at timestamp without time zone
);

CREATE TABLE result (
    id text PRIMARY KEY,
    domain text,
    position integer,
    title text,
    url text,
    updated_at timestamp without time zone
);
