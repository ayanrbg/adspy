CREATE TABLE IF NOT EXISTS ads (
    id              VARCHAR PRIMARY KEY,
    source          VARCHAR,
    page_id         VARCHAR,
    page_name       VARCHAR,
    body            TEXT,
    title           VARCHAR,
    screenshot_url  TEXT,
    image_urls      JSONB,
    video_urls      JSONB,
    has_video       BOOLEAN DEFAULT FALSE,
    country         VARCHAR,
    niche           VARCHAR,
    niche_confidence REAL,
    start_date      DATE,
    stop_date       DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    days_active     INT,
    impressions_min INT,
    impressions_max INT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ads_country_niche ON ads (country, niche);
CREATE INDEX IF NOT EXISTS idx_ads_days_active   ON ads (days_active DESC);
CREATE INDEX IF NOT EXISTS idx_ads_active        ON ads (is_active);
CREATE INDEX IF NOT EXISTS idx_ads_page          ON ads (page_id);
CREATE INDEX IF NOT EXISTS idx_ads_has_video     ON ads (has_video);
