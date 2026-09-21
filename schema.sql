CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    source_category TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    positions INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    date_posted TEXT,
    title_key TEXT NOT NULL,
    duplicate_of INTEGER REFERENCES opportunities(id),
    is_backfill INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    opp_type TEXT,
    category TEXT,
    level TEXT,
    min_years INTEGER,
    deadline TEXT,
    deadline_note TEXT,
    is_bundle INTEGER NOT NULL DEFAULT 0,
    classified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_opportunities_title_key ON opportunities(title_key);
CREATE INDEX IF NOT EXISTS idx_opportunities_first_seen ON opportunities(first_seen_at);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    listings_found INTEGER NOT NULL DEFAULT 0,
    new_found INTEGER NOT NULL DEFAULT 0,
    error TEXT
);