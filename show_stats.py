import sqlite3, json

conn = sqlite3.connect("medical.db")
conn.row_factory = sqlite3.Row

stats = dict(conn.execute("""
    SELECT site, COUNT(*) as cnt FROM articles GROUP BY site
""").fetchall())
total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
recent = conn.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now','-7 days')").fetchone()[0]

print(f"总文章数: {total}")
print(f"最近7天: {recent}")
print(json.dumps(stats, ensure_ascii=False))

print("\n=== 所有文章标题 ===")
rows = conn.execute("""
    SELECT title, site, url, reading_time, language,
           SUBSTR(content, 1, 80) as content_preview
    FROM articles ORDER BY site, title
""").fetchall()
for i, r in enumerate(rows, 1):
    print(f"{i:2}. [{r['site'].upper():4}] {r['title'][:65]}")
    print(f"    {r['url'][:90]}")
    if r['reading_time']:
        print(f"    ~{r['reading_time']} min read")
