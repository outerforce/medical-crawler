"""
Mayo Clinic 乳腺癌爬虫
https://www.mayoclinic.org/diseases-conditions/breast-cancer
"""
import hashlib
import time
import re
import requests
from typing import Optional
from bs4 import BeautifulSoup


SITE = "mayo"
BASE_URL = "https://www.mayoclinic.org"

# Mayo Clinic 乳腺癌相关页面
SUB_PAGES = [
    ("/diseases-conditions/breast-cancer/symptoms-causes/syc-20352470", "article", "Symptoms & Causes"),
    ("/diseases-conditions/breast-cancer/diagnosis-treatment/syc-20352470", "article", "Diagnosis & Treatment"),
    ("/diseases-conditions/breast-cancer/management-care/syc-20352470", "article", "Management & Care"),
    ("/diseases-conditions/breast-cancer/prevention/syc-20352470", "article", "Prevention"),
    ("/diseases-conditions/breast-cancer/screening/syc-20352470", "article", "Screening"),
    ("/diseases-conditions/breast-cancer/risk-factors/syc-20352470", "article", "Risk Factors"),
    ("/diseases-conditions/male-breast-cancer/symptoms-causes/syc-20374768", "article", "Male Breast Cancer"),
    ("/diseases-conditions/breast-cancer/tests-diagnosis/syc-20352470", "article", "Tests & Diagnosis"),
]


class MayoCrawler:
    PLATFORM = SITE
    DELAY = 4
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.mayoclinic.org/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        })

    def _generate_id(self, url: str, title: str = "") -> str:
        raw = f"{SITE}_{url}_{title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]

    def _fetch(self, path: str) -> Optional[str]:
        url = BASE_URL + path
        try:
            resp = self.session.get(url, timeout=self.TIMEOUT)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 404:
                print(f"  ⚠️ 404: {url}")
            else:
                print(f"  ⚠️ HTTP {resp.status_code}: {url}")
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
        return None

    def _clean_content(self, elem) -> str:
        if not elem:
            return ""
        for tag in elem.find_all(["script", "style", "nav", "aside", "footer", "header",
                                   "div[class*='ad']", "div[class*='promo']",
                                   "div[class*='social']", "div[class*='related']"]):
            tag.decompose()
        text = elem.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)

    def _parse_article(self, path: str, page_type: str, section: str) -> list:
        html = self._fetch(path)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        tags = ["Mayo Clinic", "breast cancer", section.lower()]

        # 标题
        title = ""
        for h1 in soup.find_all("h1"):
            text = h1.get_text(strip=True)
            if text and len(text) > 3:
                title = text
                break

        # 作者
        author = ""
        author_elem = soup.find("meta", {"name": "author"})
        if author_elem:
            author = author_elem.get("content", "")

        # 发布/更新时间
        publish_date = None
        last_updated = None
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "")
            if prop == "article:published_time":
                publish_date = meta.get("content", "")[:10]
            elif prop == "article:modified_time":
                last_updated = meta.get("content", "")[:10]

        # 正文
        main_content = (
            soup.find("article") or
            soup.find("div", {"id": re.compile(r"content|article", re.I)}) or
            soup.find("section", {"class": re.compile(r"content|body", re.I)}) or
            soup.find("main")
        )
        content_text = self._clean_content(main_content)

        # 摘要
        summary = ""
        desc_elem = soup.find("meta", {"name": "description"}) or \
                    soup.find("meta", {"property": "og:description"})
        if desc_elem:
            summary = desc_elem.get("content", "").strip()
        elif content_text:
            summary = content_text[:300] + "..." if len(content_text) > 300 else content_text

        reading_time = max(1, len(content_text) // 500) if content_text else 1

        article_id = self._generate_id(path, title)
        return [{
            "article_id": article_id,
            "site": SITE,
            "url": BASE_URL + path,
            "title": title or section,
            "summary": summary,
            "content": content_text,
            "author": author or "Mayo Clinic Staff",
            "publish_date": publish_date,
            "last_updated": last_updated,
            "reading_time": reading_time,
            "language": "en",
            "tags": tags,
        }]

    def crawl(self) -> list:
        all_articles = []
        print(f"🏥 [{SITE.upper()}] Mayo Clinic 爬虫启动，共 {len(SUB_PAGES)} 个页面")

        for i, (path, page_type, section) in enumerate(SUB_PAGES, 1):
            print(f"  [{i}/{len(SUB_PAGES)}] {section} ...", end=" ", flush=True)
            articles = self._parse_article(path, page_type, section)
            print(f"✅ {len(articles)} 条")
            all_articles.extend(articles)
            if i < len(SUB_PAGES):
                time.sleep(self.DELAY)

        return all_articles
