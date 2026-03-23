"""
独立脚本：读取本地数据库，推送 Slack 报告
用法: python slack_report.py
"""
import sqlite3, json, sys, os
from datetime import datetime

SITE_NAMES = {
    "nci":   "National Cancer Institute",
    "mayo":  "Mayo Clinic",
    "webmd": "WebMD",
    "bco":   "Breastcancer.org",
    "acs":   "American Cancer Society",
}

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "medical.db")

def get_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 统计
    stats = {"total": 0, "recent": 0, "by_site": {}}
    row = conn.execute("SELECT COUNT(*) as c FROM articles").fetchone()
    stats["total"] = row["c"] if row else 0
    row = conn.execute("SELECT COUNT(*) as c FROM articles WHERE date(updated_at) >= date('now','-7 days')").fetchone()
    stats["recent"] = row["c"] if row else 0
    for r in conn.execute("SELECT site, COUNT(*) as c FROM articles GROUP BY site").fetchall():
        stats["by_site"][r["site"]] = r["c"]

    # 各站示例文章（每站2篇）
    site_examples = {}
    for row in conn.execute("SELECT title, site, url, reading_time, summary FROM articles ORDER BY updated_at DESC").fetchall():
        s = row["site"]
        if len(site_examples.get(s, [])) >= 2:
            continue
        site_examples.setdefault(s, []).append({
            "title": row["title"] or "(无标题)",
            "url": row["url"] or "",
            "reading_time": row["reading_time"],
            "summary": row["summary"] or "",
        })
    conn.close()
    return stats, site_examples


def build_blocks(stats, site_examples):
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 乳腺癌医学资料 — 爬取报告", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"_*总文章数*_\n{stats['total']} 篇"},
                {"type": "mrkdwn", "text": f"_*近7天新增*_\n{stats['recent']} 篇"},
            ]
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*📍 各站数据分布*"}},
    ]

    site_fields = []
    for site, count in stats["by_site"].items():
        name = SITE_NAMES.get(site, site)
        site_fields.append({"type": "mrkdwn", "text": f"*{name}*\n{count} 篇"})
    if site_fields:
        blocks.append({"type": "section", "fields": site_fields})

    blocks.append({"type": "divider"})

    for site, name in SITE_NAMES.items():
        if site not in site_examples:
            continue
        articles = site_examples[site]
        lines = []
        for a in articles:
            title = (a["title"][:52] + "…") if len(a["title"]) > 52 else a["title"]
            rt = f" `{a['reading_time']}min`" if a["reading_time"] else ""
            lines.append(f"• <{a['url']}|{title}>{rt}")
        if lines:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{name}*\n" + "\n".join(lines)}
            })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | NCI · WebMD · Mayo · Breastcancer.org · ACS"
        }]
    })
    return blocks


if __name__ == "__main__":
    print("📖 读取数据库中 ...")
    stats, site_examples = get_data()
    print(f"  总文章: {stats['total']}  近7天: {stats['recent']}")
    for s, c in stats["by_site"].items():
        print(f"  [{s}] {SITE_NAMES.get(s,s)}: {c} 篇")

    blocks = build_blocks(stats, site_examples)
    print(f"\n✅ 生成 {len(blocks)} 个 Block")

    # 输出 JSON 供调试
    with open("slack_blocks.json", "w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)
    print("💾 已保存 slack_blocks.json")
