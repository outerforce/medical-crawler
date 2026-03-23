"""
数据库管理模块
"""
import sqlite3
import json
import os
from datetime import datetime


class MedicalDB:
    """乳腺癌医学资料数据库"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "data", "medical.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库（执行 schema.sql）"""
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                sql = f.read()
            conn = self._get_conn()
            conn.executescript(sql)
            conn.commit()
            conn.close()

    # ── 站点配置 ────────────────────────────────────────

    def upsert_site_config(self, site, base_url, config_json=None):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO site_configs (site, base_url, config_json)
            VALUES (?, ?, ?)
            ON CONFLICT(site) DO UPDATE SET
                base_url=excluded.base_url,
                config_json=excluded.config_json
        """, (site, base_url, json.dumps(config_json or {})))
        conn.commit()
        conn.close()

    def get_site_config(self, site):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM site_configs WHERE site=?", (site,)
        ).fetchone()
        conn.close()
        if row:
            cols = [d[0] for d in conn.execute("SELECT * FROM site_configs LIMIT 0").description]
            return dict(zip(cols, row)) if not cols else None
        return None

    def update_last_crawled(self, site):
        conn = self._get_conn()
        conn.execute(
            "UPDATE site_configs SET last_crawled=CURRENT_TIMESTAMP WHERE site=?",
            (site,)
        )
        conn.commit()
        conn.close()

    # ── 文章操作 ──────────────────────────────────────────

    def upsert_article(self, article: dict) -> bool:
        """
        插入或更新文章
        article 包含: article_id, site, url, title, summary, content,
                      author, publish_date, last_updated, reading_time, language
        返回: 是否为新插入
        """
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT id FROM articles WHERE article_id=?",
            (article["article_id"],)
        ).fetchone()

        now = datetime.now().isoformat()
        if existing:
            conn.execute("""
                UPDATE articles SET
                    url=?, title=?, summary=?, content=?,
                    author=?, publish_date=?, last_updated=?,
                    reading_time=?, updated_at=?
                WHERE article_id=?
            """, (
                article.get("url"), article.get("title"), article.get("summary"),
                article.get("content"), article.get("author"),
                article.get("publish_date"), article.get("last_updated", now),
                article.get("reading_time"), now,
                article["article_id"]
            ))
            is_new = False
        else:
            conn.execute("""
                INSERT INTO articles (
                    article_id, site, url, title, summary, content,
                    author, publish_date, last_updated, reading_time, language
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article["article_id"], article["site"], article.get("url"),
                article.get("title"), article.get("summary"), article.get("content"),
                article.get("author"), article.get("publish_date"),
                article.get("last_updated", now),
                article.get("reading_time"), article.get("language", "en")
            ))
            is_new = True

        conn.commit()
        conn.close()
        return is_new

    def add_tags(self, article_id: str, tags: list):
        conn = self._get_conn()
        for tag in tags:
            conn.execute("""
                INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)
            """, (article_id, tag))
        conn.commit()
        conn.close()

    def add_medical_terms(self, article_id: str, terms: list):
        """terms: [{term, definition, category}]"""
        conn = self._get_conn()
        for t in terms:
            conn.execute("""
                INSERT OR IGNORE INTO medical_terms
                (article_id, term, definition, category) VALUES (?, ?, ?, ?)
            """, (article_id, t["term"], t.get("definition", ""), t.get("category", "")))
        conn.commit()
        conn.close()

    def upsert_source_page(self, site: str, url: str, title: str, page_type: str, section: str = ""):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO source_pages (site, url, title, page_type, section)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET title=excluded.title, section=excluded.section
        """, (site, url, title, page_type, section))
        conn.commit()
        conn.close()

    # ── 爬虫日志 ──────────────────────────────────────────

    def start_crawl_log(self, site: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT INTO crawl_logs (site, started_at, status) VALUES (?, ?, 'running')
        """, (site, datetime.now().isoformat()))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    def finish_crawl_log(self, log_id: int, status: str, new_count: int = 0,
                          updated_count: int = 0, error_msg: str = ""):
        conn = self._get_conn()
        finished = datetime.now().isoformat()
        row = conn.execute(
            "SELECT started_at FROM crawl_logs WHERE id=?", (log_id,)
        ).fetchone()
        duration = 0
        if row and row[0]:
            started = datetime.fromisoformat(row[0])
            duration = int((datetime.now() - started).total_seconds())

        conn.execute("""
            UPDATE crawl_logs SET
                finished_at=?, status=?,
                articles_new=?, articles_updated=?,
                error_msg=?, duration_sec=?
            WHERE id=?
        """, (finished, status, new_count, updated_count, error_msg, duration, log_id))
        conn.commit()
        conn.close()

    # ── 查询 ─────────────────────────────────────────────

    def get_articles(self, site: str = None, limit: int = 50, offset: int = 0):
        conn = self._get_conn()
        if site:
            rows = conn.execute("""
                SELECT * FROM articles WHERE site=? ORDER BY updated_at DESC LIMIT ? OFFSET ?
            """, (site, limit, offset)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM articles ORDER BY updated_at DESC LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
        conn.close()
        cols = [d[0] for d in conn.execute("SELECT * FROM articles LIMIT 0").description]
        return [dict(zip(cols, r)) for r in rows]

    def search_articles(self, keyword: str, limit: int = 20):
        conn = self._get_conn()
        pattern = f"%{keyword}%"
        rows = conn.execute("""
            SELECT * FROM articles
            WHERE title LIKE ? OR summary LIKE ? OR content LIKE ?
            ORDER BY updated_at DESC LIMIT ?
        """, (pattern, pattern, pattern, limit)).fetchall()
        conn.close()
        cols = [d[0] for d in conn.execute("SELECT * FROM articles LIMIT 0").description]
        return [dict(zip(cols, r)) for r in rows]

    def get_statistics(self) -> dict:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        by_site = dict(conn.execute(
            "SELECT site, COUNT(*) FROM articles GROUP BY site"
        ).fetchall())
        by_lang = dict(conn.execute(
            "SELECT language, COUNT(*) FROM articles GROUP BY language"
        ).fetchall())
        recent = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE date(updated_at) >= date('now', '-7 days')"
        ).fetchone()[0]
        conn.close()
        return {
            "total_articles": total,
            "by_site": by_site,
            "by_language": by_lang,
            "recent_7_days": recent
        }
