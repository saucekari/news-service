import asyncio
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .base_ingester import BaseIngester


class RedditParser(BaseIngester):
    def __init__(self, subreddit: str = "python", limit: int = 5, *args, **kwargs):
        # Переди имя источника в базовый класс
        super().__init__(source_name=f"reddit:r/{subreddit}", *args, **kwargs)
        self.subreddit = subreddit
        self.limit = limit
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _sync_fetch(self) -> list:
        """Синхронный метод парсинга Reddit через Playwright."""
        url = f"https://old.reddit.com/r/{self.subreddit}/new/"
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=self.ua,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                soup = BeautifulSoup(page.content(), "html.parser")
                posts = soup.find_all("div", class_="thing")[:self.limit]
                
                for post in posts:
                    title_attr = post.find("a", class_="title")
                    if not title_attr:
                        continue
                    
                    author_tag = post.find("a", class_="author")
                    score_tag = post.find("div", class_="score unvoted")
                    
                    results.append({
                        "title": title_attr.text,
                        "text": title_attr.text,  # Для унификации з анализатором
                        "url": title_attr["href"] if title_attr["href"].startswith("http") else f"https://old.reddit.com{title_attr['href']}",
                        "author": author_tag.text if author_tag else "Unknown",
                        "score": score_tag.text.strip() if score_tag else "0",
                    })
            except Exception as e:
                print(f"Помилка RedditParser для r/{self.subreddit}: {e}")
            finally:
                browser.close()
        return results

    async def fetch(self) -> dict:
        """Асинхронна обгортка для запуску синхронного Playwright в окремому потоці."""
        items = await asyncio.to_thread(self._sync_fetch)
        return {
            "source": self.source_name,
            "items": items
        }