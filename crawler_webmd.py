"""
WebMD 乳腺癌爬虫
https://www.webmd.com/breast-cancer
"""
import hashlib
import time
import re
import requests
from bs4 import BeautifulSoup


SITE = "webmd"
BASE_URL = "https://www.webmd.com"

# WebMD 乳腺癌章节URL
CHAPTERS = [
    ("/breast-cancer/guide-chapter-breast-cancer-overview", "guide", "Overview"),
    ("/breast-cancer/guide-chapter-breast-cancer-symptoms", "guide", "Symptoms"),
    ("/breast-cancer/guide-chapter-breast-cancer-risks", "guide", "Risks & Prevention"),
    ("/breast-cancer/guide-chapter-breast-cancer-diagnosis", "guide", "Tests & Diagnosis"),
    ("/breast-cancer/guide-chapter-breast-cancer-types", "guide", "Types"),
    ("/breast-cancer/guide-chapter-breast-cancer-treatment-team", "guide", "Care Team"),
    ("/breast-cancer/guide-chapter-breast-cancer-treatment", "guide", "Treatment"),
    ("/breast-cancer/guide-chapter-breast-cancer-living", "guide", "Living With"),
    ("/breast-cancer/guide-chapter-breast-cancer-remission", "guide", "Remission & Recurrence"),
    ("/breast-cancer/guide-chapter-breast-cancer-advanced", "guide", "Advanced"),
    ("/breast-cancer/guide-chapter-breast-cancer-support", "guide", "Support & Resources"),
    ("/breast-cancer/guide-chapter-breast-cancer-appointment-prep", "guide", "Appointment Prep"),
    # 主要文章页
    ("/breast-cancer/understanding-breast-cancer-basics", "article", "Breast Cancer Basics"),
    ("/breast-cancer/breast-cancer-symptoms-what-women-know", "article", "Symptoms Facts"),
    ("/breast-cancer/breast-cancer-screening-exams", "article", "Screening Exams"),
    ("/breast-cancer/quizzes/breast-cancer-risk-quiz", "article", "Risk Quiz"),
]


class WebMDCrawler:
    PLATFORM = SITE
    DELAY = 3
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.webmd.com/",
        })

    def _generate_id(self, url: str, title: str = "") -> str:
        raw = f"{SITE}_{url}_{title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]

    def _fetch(self, path: str) -> str | None:
        url = BASE_URL + path if path.startswith("/") else path
        try:
            resp = self.session.get(url, timeout=self.TIMEOUT)
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"  ⚠️ HTTP {resp.status_code}: {url}")
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
        return None

    def _clean_content(self, elem) -> str:
        if not elem:
            return ""
        for tag in elem.find_all(["script", "style", "nav", "aside", "footer",
                                   "div[class*='ad']", "div[class*='promo']",
                                   "div[class*='newsletter']", "div[class*='social']",
                                   "div[class*='related']", "div[class*='sticky']"]):
            tag.decompose()
        text = elem.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)

    def _parse_page(self, path: str, page_type: str, section: str) -> list:
        html = self._fetch(path)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = []
        tags = ["WebMD", "breast cancer", section.lower()]

        # 尝试提取所有文章链接（guide页有多个文章）
        if page_type == "guide":
            # guide页：提取当前章节内容 + 子文章链接
            main_content = (
                soup.find("article") or
                soup.find("div", {"class": re.compile(r"article-content|content-area|main-content", re.I)}) or
                soup.find("main") or
                soup.find("div", {"id": "content"})
            )

            if main_content:
                content_text = self._clean_content(main_content)
                title = ""
                title_elem = soup.find("h1")
                if title_elem:
                    title = title_elem.get_text(strip=True)

                summary = ""
                desc_elem = soup.find("meta", {"name": "description"})
                if desc_elem:
                    summary = desc_elem.get("content", "").strip()

                article_id = self._generate_id(path, title)
                articles.append({
                    "article_id": article_id,
                    "site": SITE,
                    "url": BASE_URL + path if path.startswith("/") else path,
                    "title": title or f"WebMD Breast Cancer - {section}",
                    "summary": summary,
                    "content": content_text,
                    "author": "WebMD Medical Editorial Team",
                    "publish_date": None,
                    "last_updated": None,
                    "reading_time": max(1, len(content_text) // 500) if content_text else 1,
                    "language": "en",
                    "tags": tags,
                })

            # 同时收集子页面链接
            for link in soup.select("div.section-content a[href*='/breast-cancer/']"):
                href = link.get("href", "")
                if not href or "javascript" in href or href == "#":
                    continue
                link_title = link.get_text(strip=True)
                if not link_title or len(link_title) < 5:
                    continue
                article_id = self._generate_id(href, link_title)
                articles.append({
                    "article_id": article_id,
                    "site": SITE,
                    "url": BASE_URL + href if href.startswith("/") else href,
                    "title": link_title,
                    "summary": "",
                    "content": "",
                    "author": "WebMD Medical Editorial Team",
                    "publish_date": None,
                    "last_updated": None,
                    "reading_time": None,
                    "language": "en",
                    "tags": tags,
                })

        else:
            # 普通文章页
            title = ""
            for h1 in soup.find_all(["h1", "h2"]):
                text = h1.get_text(strip=True)
                if text and len(text) > 3:
                    title = text
                    break

            main_content = (
                soup.find("article") or
                soup.find("div", {"class": re.compile(r"article-content|article-body", re.I)}) or
                soup.find("main")
            )
            content_text = self._clean_content(main_content)

            summary = ""
            desc_elem = soup.find("meta", {"property": "og:description"}) or \
                        soup.find("meta", {"name": "description"})
            if desc_elem:
                summary = desc_elem.get("content", "").strip()

            article_id = self._generate_id(path, title)
            articles.append({
                "article_id": article_id,
                "site": SITE,
                "url": BASE_URL + path if path.startswith("/") else path,
                "title": title or section,
                "summary": summary,
                "content": content_text,
                "author": "WebMD Medical Editorial Team",
                "publish_date": None,
                "last_updated": None,
                "reading_time": max(1, len(content_text) // 500) if content_text else 1,
                "language": "en",
                "tags": tags,
            })

        return articles

    def crawl(self) -> list:
        all_articles = []
        print(f"🏥 [{SITE.upper()}] WebMD 爬虫启动，共 {len(CHAPTERS)} 个页面")

        for i, (path, page_type, section) in enumerate(CHAPTERS, 1):
            print(f"  [{i}/{len(CHAPTERS)}] {section} ...", end=" ", flush=True)
            articles = self._parse_page(path, page_type, section)
            print(f"✅ {len(articles)} 条")
            all_articles.extend(articles)
            if i < len(CHAPTERS):
                time.sleep(self.DELAY)

        return all_articles
