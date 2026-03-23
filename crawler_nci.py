"""
NCI (National Cancer Institute) 乳腺癌爬虫
https://www.cancer.gov/types/breast
"""
import hashlib
import time
import re
import requests
from bs4 import BeautifulSoup


SITE = "nci"
BASE_URL = "https://www.cancer.gov"

# NCI 乳腺癌专题页的所有子页面URL
SUB_PAGES = [
    ("/types/breast", "index", "Breast Cancer Home"),
    ("/types/breast/what-is-breast-cancer", "article", "What Is Breast Cancer"),
    ("/types/breast/breast-cancer-types", "article", "Breast Cancer Types"),
    ("/types/breast/causes-risk-factors", "article", "Causes and Risk Factors"),
    ("/types/breast/symptoms", "article", "Signs and Symptoms"),
    ("/types/breast/screening", "article", "Screening"),
    ("/types/breast/diagnosis", "article", "Diagnosis"),
    ("/types/breast/stages", "article", "Stages"),
    ("/types/breast/treatment", "article", "Treatment"),
    ("/types/breast/survival", "article", "Prognosis and Survival Rates"),
    ("/types/breast/breast-cancer-survivorship", "article", "Survivorship"),
    ("/types/breast/male-breast-cancer", "article", "Male Breast Cancer"),
    ("/types/breast/breast-cancer-during-pregnancy", "article", "Pregnancy"),
    ("/types/breast/research", "article", "Research"),
]


class NCICrawler:
    PLATFORM = SITE
    DELAY = 3
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def _generate_id(self, url: str, title: str = "") -> str:
        raw = f"{SITE}_{url}_{title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]

    def _fetch(self, path: str) -> str | None:
        url = BASE_URL + path
        try:
            resp = self.session.get(url, timeout=self.TIMEOUT)
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"  ⚠️ HTTP {resp.status_code}: {url}")
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
        return None

    def _parse_article(self, path: str, page_type: str, section: str) -> list:
        """解析单个页面，返回文章列表"""
        html = self._fetch(path)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = []

        # 提取面包屑/分类
        breadcrumb = []
        for crumb in soup.select(".breadcrumbs a, nav.breadcrumb a, [class*='breadcrumb'] a"):
            text = crumb.get_text(strip=True)
            if text and text not in breadcrumb:
                breadcrumb.append(text)
        tags = breadcrumb + [section, "breast cancer", "cancer"]

        if page_type == "index":
            # 索引页：提取所有子链接
            for link in soup.select("a[href*='/types/breast']"):
                href = link.get("href", "")
                if not href or href.startswith("#") or "javascript" in href:
                    continue
                title_text = link.get_text(strip=True)
                if not title_text or len(title_text) < 5:
                    continue
                article_id = self._generate_id(href, title_text)
                articles.append({
                    "article_id": article_id,
                    "site": SITE,
                    "url": BASE_URL + href if href.startswith("/") else href,
                    "title": title_text,
                    "summary": "",
                    "content": "",
                    "author": "National Cancer Institute",
                    "publish_date": None,
                    "last_updated": None,
                    "reading_time": None,
                    "language": "en",
                    "tags": list(set(tags)),
                })
        else:
            # 文章页：提取全文
            title = ""
            title_elem = soup.find("h1")
            if title_elem:
                title = title_elem.get_text(strip=True)

            # 发布时间
            publish_date = None
            for meta in soup.find_all("meta"):
                if meta.get("property") == "article:published_time":
                    publish_date = meta.get("content", "")[:10]
                    break
                if meta.get("name") in ("citation_publication_date", "DC.date"):
                    publish_date = meta.get("content", "")[:10]
                    break

            # 更新时间
            last_updated = None
            for meta in soup.find_all("meta"):
                if meta.get("property") == "article:modified_time":
                    last_updated = meta.get("content", "")[:10]
                    break

            # 正文内容
            content_elem = (
                soup.find("article") or
                soup.find("div", {"id": "article-content"}) or
                soup.find("div", {"class": re.compile(r"article|content", re.I)}) or
                soup.find("main") or
                soup.find("div", {"id": "main-content"})
            )

            content_text = ""
            if content_elem:
                # 移除脚本和样式
                for tag in content_elem.find_all(["script", "style", "nav", "aside"]):
                    tag.decompose()
                content_text = content_elem.get_text(separator="\n", strip=True)
                content_text = re.sub(r"\n{3,}", "\n\n", content_text)

            # 摘要
            summary = ""
            desc_elem = soup.find("meta", {"name": "description"})
            if desc_elem:
                summary = desc_elem.get("content", "").strip()
            elif content_text:
                summary = content_text[:300] + "..." if len(content_text) > 300 else content_text

            # 阅读时长（粗略估算：每500字符1分钟）
            reading_time = max(1, len(content_text) // 500) if content_text else 1

            article_id = self._generate_id(path, title)
            articles.append({
                "article_id": article_id,
                "site": SITE,
                "url": BASE_URL + path,
                "title": title or section,
                "summary": summary,
                "content": content_text,
                "author": "National Cancer Institute",
                "publish_date": publish_date,
                "last_updated": last_updated,
                "reading_time": reading_time,
                "language": "en",
                "tags": list(set(tags)),
            })

        return articles

    def crawl(self) -> list:
        """爬取 NCI 所有页面"""
        all_articles = []
        print(f"🏥 [{SITE.upper()}] NCI 爬虫启动，共 {len(SUB_PAGES)} 个页面")

        for i, (path, page_type, section) in enumerate(SUB_PAGES, 1):
            print(f"  [{i}/{len(SUB_PAGES)}] {section} ...", end=" ", flush=True)
            articles = self._parse_article(path, page_type, section)
            print(f"✅ {len(articles)} 条")
            all_articles.extend(articles)
            if i < len(SUB_PAGES):
                time.sleep(self.DELAY)

        return all_articles
