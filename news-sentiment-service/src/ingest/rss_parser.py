import asyncio
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from .base_ingester import BaseIngester


class RSSParser(BaseIngester):
    def __init__(self, rss_url: str, source_display_name: str, limit: int = 3, *args, **kwargs):
        super().__init__(source_name=source_display_name.lower(), *args, **kwargs)
        self.rss_url = rss_url
        self.source_display_name = source_display_name
        self.limit = limit
        self.browser_impersonate = "chrome124"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _check_class(self, x, search_keywords) -> bool:
        if not x:
            return False
        classes_str = (" ".join(x) if isinstance(x, list) else str(x)).lower()
        return any(k in classes_str for k in search_keywords)

    def _parse_full_article_text(self, url: str) -> str:
        try:
            response = curl_requests.get(
                url,
                headers=self.headers,
                impersonate=self.browser_impersonate,
                timeout=15,
            )
            if response.status_code != 200:
                return f"[Ошибка загрузки контента: Статус {response.status_code}]"

            soup = BeautifulSoup(response.content, "html.parser")
            paragraphs = []

            # 1. Специфика CoinDesk
            if "coindesk" in self.source_name:
                content_blocks = soup.find_all(
                    ["div", "section"],
                    class_=lambda x: self._check_class(x, ["common-textstyles", "typography", "composer"]),
                )
                for block in content_blocks:
                    for p in block.find_all("p"):
                        if p.text.strip():
                            paragraphs.append(p.text.strip())

            # 2. Специфика Cointelegraph
            elif "cointelegraph" in self.source_name:
                content_block = soup.find(
                    "div",
                    class_=lambda x: self._check_class(x, ["post-content", "post__text", "article__body"]),
                )
                if not content_block:
                    content_block = soup.find("article")

                if content_block:
                    for p in content_block.find_all("p"):
                        p_text = p.text.strip()
                        if p_text and not any(k in p_text.lower() for k in ["read more", "related:", "at/"]):
                            paragraphs.append(p_text)

            # 3. Универсальний фолбек (Yahoo и другие)
            if not paragraphs:
                target = soup.find("article") or soup.find("div", class_="caas-body") or soup.find("main") or soup.body
                if target:
                    for p in target.find_all("p"):
                        p_text = p.text.strip()
                        if len(p_text) > 50 and not any(k in p_text.lower() for k in ["terms of service", "privacy policy", "cookie policy"]):
                            paragraphs.append(p_text)

            return self._clean_text(" ".join(paragraphs)) if paragraphs else "[Текст пуст]"

        except Exception as e:
            return f"[Ошибка скрапинга текста: {e}]"

    def _sync_fetch(self) -> list:
        results = []
        try:
            response = curl_requests.get(
                self.rss_url,
                headers=self.headers,
                impersonate=self.browser_impersonate,
                timeout=15,
            )
            if response.status_code != 200:
                return []

            root = ET.fromstring(response.content)
            items = root.findall(".//item")[:self.limit]

            for item in items:
                title_node = item.find("title")
                link_node = item.find("link")
                date_node = item.find("pubDate")

                title = title_node.text if title_node is not None else ""
                link = link_node.text if link_node is not None else ""
                pub_date = date_node.text if date_node is not None else ""

                if not link:
                    continue

                full_text = self._parse_full_article_text(link.strip())

                results.append({
                    "source": self.source_display_name,
                    "title": title.strip(),
                    "text": full_text,  # Передаем весь текст как головное поле для LLM-анализа
                    "url": link.strip(),
                    "date": pub_date.strip(),
                })
        except Exception as e:
            print(f"Помилка RSS фреймворку для {self.source_display_name}: {e}")
        return results

    async def fetch(self) -> dict:
        items = await asyncio.to_thread(self._sync_fetch)
        return {
            "source": self.source_name,
            "items": items
        }