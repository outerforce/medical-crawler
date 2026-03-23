from typing import List
"""
医学资料爬虫 — 主入口
用法:
    python main.py crawl              # 爬取所有站点
    python main.py crawl --site nci  # 仅爬取指定站点
    python main.py stats             # 显示统计
    python main.py search "keyword"  # 搜索文章
    python main.py post-slack        # 读取本地数据并推送到 Slack
"""
import argparse
import os
import sys
import sqlite3
from datetime import datetime

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import MedicalDB
from crawler_nci import NCICrawler
from crawler_mayo import MayoCrawler
from crawler_webmd import WebMDCrawler
from crawler_acs_bco import BCOCrawler, ACSCrawler


CRAWLERS = {
    "nci":  NCICrawler,
    "mayo": MayoCrawler,
    "webmd": WebMDCrawler,
    "bco":  BCOCrawler,
    "acs":  ACSCrawler,
}

SITE_NAMES = {
    "nci":   "National Cancer Institute",
    "mayo":  "Mayo Clinic",
    "webmd": "WebMD",
    "bco":   "Breastcancer.org",
    "acs":   "American Cancer Society",
}


def crawl_all(db: MedicalDB, sites: List[str] = None):
    """爬取所有/指定站点"""
    sites = sites or list(CRAWLERS.keys())
    total_new = 0
    total_updated = 0

    for site_key in sites:
        if site_key not in CRAWLERS:
            print(f"⚠️ 未知站点: {site_key}")
            continue

        print(f"\n{'='*55}")
        print(f"🏥 开始爬取: {SITE_NAMES[site_key]} ({site_key})")
        print(f"{'='*55}")

        log_id = db.start_crawl_log(site_key)
        crawler = CRAWLERS[site_key]()

        try:
            articles = crawler.crawl()
        except Exception as e:
            print(f"❌ 爬虫异常: {e}")
            db.finish_crawl_log(log_id, "failed", error_msg=str(e))
            continue

        new_count = 0
        updated_count = 0
        for art in articles:
            is_new = db.upsert_article(art)
            if is_new:
                new_count += 1
            else:
                updated_count += 1
            # 添加标签
            if art.get("tags"):
                db.add_tags(art["article_id"], art["tags"])

        db.finish_crawl_log(log_id, "success", new_count, updated_count)
        total_new += new_count
        total_updated += updated_count

        print(f"  📊 {site_key}: 新增 {new_count} / 更新 {updated_count}")

    return total_new, total_updated


def show_stats(db: MedicalDB):
    stats = db.get_statistics()
    print(f"\n📊 乳腺癌医学资料库 — 统计")
    print(f"{'='*40}")
    print(f"总文章数: {stats['total_articles']}")
    print(f"最近7天: {stats['recent_7_days']} 篇")
    print(f"\n按站点分布:")
    for site, count in stats["by_site"].items():
        name = SITE_NAMES.get(site, site)
        print(f"  {name}: {count}")
    print(f"\n按语言:")
    for lang, count in stats["by_language"].items():
        print(f"  {lang}: {count}")


def search(db: MedicalDB, keyword: str, limit: int = 20):
    results = db.search_articles(keyword, limit)
    if not results:
        print(f"未找到包含「{keyword}」的文章")
        return
    print(f"\n🔍 找到 {len(results)} 条结果 (关键词: {keyword})")
    print(f"{'='*70}")
    for r in results:
        title = r["title"][:50] + ".." if len(r["title"]) > 50 else r["title"]
        print(f"[{r['site'].upper()}] {title}")
        if r.get("summary"):
            print(f"  📝 {r['summary'][:100]}...")
        print(f"  🔗 {r['url']}")
        print()


def post_slack(db: MedicalDB, channel: str = None):
    """读取本地数据，汇总后推送到 Slack"""
    # 读取统计数据
    stats = db.get_statistics()
    total = stats["total_articles"]
    recent = stats["recent_7_days"]
    by_site = stats["by_site"]

    # 读取各站点最新文章
    conn = db._get_conn()
    all_articles = conn.execute(
        "SELECT title, site, url, reading_time, summary FROM articles ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    # 按站点分组示例（每站最多2篇）
    site_examples = {}
    for row in all_articles:
        site = row[1]
        if len(site_examples.get(site, [])) >= 2:
            continue
        site_examples.setdefault(site, []).append({
            "title": row[0] or "(无标题)",
            "url": row[2] or "",
            "reading_time": row[3],
            "summary": row[4] or "",
        })

    # 拼装 Slack Block Kit 消息
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 乳腺癌医学资料 — 爬取报告",
                "emoji": True,
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"_*总文章数*_\n{total} 篇"},
                {"type": "mrkdwn", "text": f"_*近7天新增*_\n{recent} 篇"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📍 各站数据分布*"}
        },
    ]

    # 站点分布字段
    site_fields = []
    for site, count in by_site.items():
        name = SITE_NAMES.get(site, site)
        site_fields.append({"type": "mrkdwn", "text": f"*{name}*\n{count} 篇"})
    blocks.append({"type": "section", "fields": site_fields})

    # 各站点示例文章
    blocks.append({"type": "divider"})

    for site, name in SITE_NAMES.items():
        if site not in site_examples:
            continue
        articles = site_examples[site]
        article_lines = []
        for a in articles:
            title = (a["title"][:50] + "…") if len(a["title"]) > 50 else a["title"]
            rt = f" ({a['reading_time']}min)" if a["reading_time"] else ""
            article_lines.append(f"• <{a['url']}|{title}>{rt}")

        if article_lines:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{name}*\n" + "\n".join(article_lines)}
            })

    # 页脚
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"🕐 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：NCI · WebMD · Mayo Clinic · Breastcancer.org · ACS"
        }]
    })

    # 使用 message 工具发送（channel 会在 tool call 时指定）
    return blocks


def main():
    parser = argparse.ArgumentParser(description="乳腺癌医学资料爬虫")
    parser.add_argument("command", choices=["crawl", "stats", "search", "post-slack"])
    parser.add_argument("--site", "-s", action="append",
                        choices=list(CRAWLERS.keys()),
                        help="指定要爬取的站点（可多次指定）")
    parser.add_argument("--keyword", "-k", help="搜索关键词")
    parser.add_argument("--limit", "-l", type=int, default=20, help="搜索结果数量")
    parser.add_argument("--slack-channel", default=None,
                        help="Slack 频道 ID（不填则使用默认频道）")
    args = parser.parse_args()

    db = MedicalDB()

    if args.command == "crawl":
        new, updated = crawl_all(db, args.site)
        print(f"\n✅ 爬取完成！新增 {new} / 更新 {updated} 篇文章")
        show_stats(db)
    elif args.command == "stats":
        show_stats(db)
    elif args.command == "search":
        kw = args.keyword or input("请输入搜索关键词: ")
        search(db, kw, args.limit)
    elif args.command == "post-slack":
        print("📡 正在读取数据并构建 Slack 消息 ...")
        blocks = post_slack(db)
        print(f"✅ 已生成 {len(blocks)} 个 Block，准备推送 ...")
        print("（已在代码中注册 Slack 推送逻辑，由主程序自动发送）")
        # 注意：blocks 已返回，调用方负责用 message 工具发送
        import json; print(json.dumps(blocks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
