"""
ACS (American Cancer Society) + Breastcancer.org 爬虫
"""
import hashlib
import time
import re
import requests
from bs4 import BeautifulSoup


# ──────────────────────────────────────────────
# Breastcancer.org
# ──────────────────────────────────────────────
SITE_BCO = "bco"
BASE_BCO = "https://www.breastcancer.org"

BCO_PAGES = [
    ("/", "index", "Home"),
    ("/types", "article", "Types"),
    ("/symptoms", "article", "Symptoms"),
    ("/diagnosis", "article", "Diagnosis"),
    ("/treatment", "article", "Treatment"),
    ("/living-with-breast-cancer", "article", "Living With Breast Cancer"),
    ("/research-news", "article", "Research News"),
]


class BCOCrawler:
    PLATFORM = SITE_BCO
    DELAY = 3
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,*/*",
            "Referer": BASE_BCO + "/",
        })

    def _gen_id(self, url, title=""):
        return hashlib.md5(f"{SITE_BCO}_{url}_{title}".encode()).hexdigest()[:20]

    def _fetch(self, path):
        url = (BASE_BCO + path) if path.startswith("/") else path
        try:
            r = self.session.get(url, timeout=self.TIMEOUT)
            return r.text if r.status_code == 200 else None
        except Exception as e:
            print(f"  ❌ {e}")
        return None

    def _clean(self, elem):
        if not elem:
            return ""
        for t in elem.find_all(["script","style","nav","aside","footer"]):
            t.decompose()
        return re.sub(r"\n{3,}", "\n\n", elem.get_text(separator="\n", strip=True))

    def _parse(self, path, page_type, section):
        html = self._fetch(path)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        if soup.find(string=re.compile(r"security check|vercel", re.I)):
            return []
        tags = ["Breastcancer.org", "breast cancer", section.lower()]
        articles = []

        if page_type == "index":
            for link in soup.select("a[href]"):
                href = link.get("href","")
                if not href or "javascript" in href or not href.startswith("/"):
                    continue
                if not any(href.startswith(p) for p in ["/types","/symptoms","/diagnosis","/treatment","/living","/research"]):
                    continue
                title_text = link.get_text(strip=True)
                if not title_text or len(title_text) < 5:
                    continue
                articles.append({
                    "article_id": self._gen_id(href, title_text),
                    "site": SITE_BCO, "url": BASE_BCO + href,
                    "title": title_text, "summary": "", "content": "",
                    "author": "Breastcancer.org Editorial Team",
                    "publish_date": None, "last_updated": None, "reading_time": None,
                    "language": "en", "tags": tags,
                })
        else:
            title = (soup.find("h1") or soup.find("h2"))
            title = title.get_text(strip=True) if title else section
            main = (soup.find("article") or soup.find("main") or
                    soup.find("div", {"class": re.compile(r"content|article", re.I)}))
            content = self._clean(main)
            summary = ""
            m = soup.find("meta", {"name": "description"})
            if m:
                summary = m.get("content","").strip()
            elif content:
                summary = content[:300]+"..."
            articles.append({
                "article_id": self._gen_id(path, title),
                "site": SITE_BCO, "url": BASE_BCO + path,
                "title": title, "summary": summary, "content": content,
                "author": "Breastcancer.org Editorial Team",
                "publish_date": None, "last_updated": None,
                "reading_time": max(1, len(content)//500) if content else 1,
                "language": "en", "tags": tags,
            })
        return articles

    def crawl(self):
        all_articles = []
        print(f"🏥 [{SITE_BCO.upper()}] Breastcancer.org 爬虫，共 {len(BCO_PAGES)} 页")
        for i, (path, pt, sec) in enumerate(BCO_PAGES, 1):
            print(f"  [{i}/{len(BCO_PAGES)}] {sec} ...", end=" ", flush=True)
            arts = self._parse(path, pt, sec)
            print(f"✅ {len(arts)} 条")
            all_articles.extend(arts)
            if i < len(BCO_PAGES):
                time.sleep(self.DELAY)
        return all_articles


# ──────────────────────────────────────────────
# ACS (American Cancer Society)
# ──────────────────────────────────────────────
SITE_ACS = "acs"
BASE_ACS = "https://www.cancer.org"

ACS_PAGES = [
    ("/cancer/types/breast-cancer/about.html", "article", "About Breast Cancer"),
    ("/cancer/types/breast-cancer/risk-and-prevention.html", "article", "Risk & Prevention"),
    ("/cancer/types/breast-cancer/screening-tests-and-early-detection.html", "article", "Early Detection"),
    ("/cancer/types/breast-cancer/understanding-a-breast-cancer-diagnosis.html", "article", "Diagnosis"),
    ("/cancer/types/breast-cancer/treatment.html", "article", "Treatment"),
    ("/cancer/types/breast-cancer/reconstruction-surgery.html", "article", "Reconstruction"),
    ("/cancer/types/breast-cancer/living-as-a-breast-cancer-survivor.html", "article", "Survivorship"),
    ("/cancer/types/breast-cancer/non-cancerous-breast-conditions.html", "article", "Non-cancerous"),
    ("/cancer/types/breast-cancer/causes-risks-genes.html", "article", "Causes & Genes"),
    ("/cancer/types/breast-cancer/research.html", "article", "Research"),
]


class ACSCrawler:
    PLATFORM = SITE_ACS
    DELAY = 3
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,*/*",
            "Referer": BASE_ACS + "/",
        })

    def _gen_id(self, url, title=""):
        return hashlib.md5(f"{SITE_ACS}_{url}_{title}".encode()).hexdigest()[:20]

    def _fetch(self, path):
        url = (BASE_ACS + path) if path.startswith("/") else path
        try:
            r = self.session.get(url, timeout=self.TIMEOUT)
            return r.text if r.status_code == 200 else None
        except Exception as e:
            print(f"  ❌ {e}")
        return None

    def _clean(self, elem):
        if not elem:
            return ""
        for t in elem.find_all(["script","style","nav","aside","footer",
                                "div[class*='ad']","div[class*='social']","div[class*='promo']"]):
            t.decompose()
        return re.sub(r"\n{3,}", "\n\n", elem.get_text(separator="\n", strip=True))

    def _parse(self, path, page_type, section):
        html = self._fetch(path)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        tags = ["American Cancer Society", "breast cancer", section.lower()]
        articles = []

        title = (soup.find("h1") or soup.find("h2"))
        title = title.get_text(strip=True) if title else section

        # 发布时间
        pub_date = None
        for meta in soup.find_all("meta"):
            p = meta.get("property","")
            if p == "article:published_time":
                pub_date = meta.get("content","")[:10]
                break

        main = (soup.find("article") or soup.find("main") or
                soup.find("div", {"id": "content-container"}) or
                soup.find("div", {"class": re.compile(r"content|article", re.I)}))
        content = self._clean(main)

        summary = ""
        m = soup.find("meta", {"property": "og:description"}) or soup.find("meta", {"name": "description"})
        if m:
            summary = m.get("content","").strip()
        elif content:
            summary = content[:300]+"..."

        articles.append({
            "article_id": self._gen_id(path, title),
            "site": SITE_ACS, "url": BASE_ACS + path,
            "title": title, "summary": summary, "content": content,
            "author": "American Cancer Society",
            "publish_date": pub_date, "last_updated": None,
            "reading_time": max(1, len(content)//500) if content else 1,
            "language": "en", "tags": tags,
        })

        # 收集同页面的子链接
        for link in soup.select("a[href*='/cancer/types/breast-cancer/']"):
            href = link.get("href","")
            if not href or "javascript" in href or href.endswith(path):
                continue
            link_title = link.get_text(strip=True)
            if not link_title or len(link_title) < 5:
                continue
            articles.append({
                "article_id": self._gen_id(href, link_title),
                "site": SITE_ACS, "url": BASE_ACS + href if href.startswith("/") else href,
                "title": link_title, "summary": "", "content": "",
                "author": "American Cancer Society",
                "publish_date": None, "last_updated": None, "reading_time": None,
                "language": "en", "tags": tags,
            })

        return articles

    def crawl(self):
        all_articles = []
        print(f"🏥 [{SITE_ACS.upper()}] ACS 爬虫，共 {len(ACS_PAGES)} 页")
        for i, (path, pt, sec) in enumerate(ACS_PAGES, 1):
            print(f"  [{i}/{len(ACS_PAGES)}] {sec} ...", end=" ", flush=True)
            arts = self._parse(path, pt, sec)
            print(f"✅ {len(arts)} 条")
            all_articles.extend(arts)
            if i < len(ACS_PAGES):
                time.sleep(self.DELAY)
        return all_articles
