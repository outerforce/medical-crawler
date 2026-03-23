-- ============================================================
-- 乳腺癌医学资料数据库表结构
-- 数据库: SQLite
-- ============================================================

-- 1. 原始页面索引（每个来源站点的入口/列表页）
CREATE TABLE IF NOT EXISTS source_pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site        TEXT    NOT NULL,          -- nci | mayo | webmd | bco | acs
    url         TEXT    NOT NULL UNIQUE,
    title       TEXT,
    page_type   TEXT    NOT NULL,          -- index | article | guide | blog
    section     TEXT,                      -- 所属栏目
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 文章主表
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      TEXT    NOT NULL UNIQUE,   -- hash(url)
    site            TEXT    NOT NULL,          -- nci | mayo | webmd | bco | acs
    url             TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    summary         TEXT,                       -- 摘要/简介
    content         TEXT,                       -- 正文全文（HTML或纯文本）
    author          TEXT,                       -- 作者
    publish_date    DATETIME,                   -- 发布日期
    last_updated    DATETIME,                   -- 最后更新时间
    reading_time    INTEGER,                   -- 阅读时长（分钟）
    language        TEXT    DEFAULT 'en',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. 文章标签/分类
CREATE TABLE IF NOT EXISTS article_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  TEXT    NOT NULL,
    tag         TEXT    NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(article_id) ON DELETE CASCADE,
    UNIQUE(article_id, tag)
);

-- 4. 文章内的医学术语提取
CREATE TABLE IF NOT EXISTS medical_terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  TEXT    NOT NULL,
    term        TEXT    NOT NULL,
    definition  TEXT,
    category    TEXT,               -- symptom | treatment | drug | stage | gene
    FOREIGN KEY (article_id) REFERENCES articles(article_id) ON DELETE CASCADE
);

-- 5. 相关文章关联（基于标签/分类的推荐）
CREATE TABLE IF NOT EXISTS related_articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      TEXT    NOT NULL,
    related_id      TEXT    NOT NULL,
    relevance_score REAL    DEFAULT 0.5,   -- 0.0~1.0
    FOREIGN KEY (article_id) REFERENCES articles(article_id) ON DELETE CASCADE,
    FOREIGN KEY (related_id)  REFERENCES articles(article_id) ON DELETE CASCADE,
    UNIQUE(article_id, related_id)
);

-- 6. 爬虫运行日志
CREATE TABLE IF NOT EXISTS crawl_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site        TEXT    NOT NULL,
    started_at  DATETIME NOT NULL,
    finished_at  DATETIME,
    status      TEXT    NOT NULL,      -- running | success | failed | partial
    articles_new INTEGER DEFAULT 0,
    articles_updated INTEGER DEFAULT 0,
    error_msg   TEXT,
    duration_sec INTEGER
);

-- 7. 站点配置（可配置爬虫参数）
CREATE TABLE IF NOT EXISTS site_configs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site        TEXT    NOT NULL UNIQUE,
    base_url    TEXT    NOT NULL,
    is_enabled  INTEGER DEFAULT 1,
    crawl_interval_hours INTEGER DEFAULT 24,
    last_crawled DATETIME,
    config_json TEXT                        -- 站点特定配置（JSON）
);

-- ============================================================
-- 索引
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_articles_site ON articles(site);
CREATE INDEX IF NOT EXISTS idx_articles_pubdate ON articles(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language);
CREATE INDEX IF NOT EXISTS idx_tags_article ON article_tags(article_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON article_tags(tag);
CREATE INDEX IF NOT EXISTS idx_terms_article ON medical_terms(article_id);
CREATE INDEX IF NOT EXISTS idx_logs_site ON crawl_logs(site);
