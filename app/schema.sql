CREATE TABLE IF NOT EXISTS card_counts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    count     INTEGER NOT NULL,
    shift     INTEGER NOT NULL CHECK (shift IN (1, 2, 3)),
    date_time TEXT    NOT NULL  -- 'YYYY-MM-DD HH:MM:SS'
);

CREATE INDEX IF NOT EXISTS idx_card_shift_time ON card_counts (shift, date_time);