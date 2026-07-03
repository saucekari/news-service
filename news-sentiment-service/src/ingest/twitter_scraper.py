import asyncio
import os
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_ingester import BaseIngester


class TwitterScraper(BaseIngester):
    """Скрапер ленты/профилей X (Twitter) через Playwright с авторизацией.

    X отдаёт meaningful-контент только залогиненным пользователям, поэтому
    скрапинг держится на сохранённом ``storage_state`` (cookies + localStorage),
    который один раз получает человек в реальном браузере и экспортирует в JSON.

    Способ первичного получения ``storage_state``::

        # 1) запустить playwright-код, который открывает окно и ждёт ручного логина:
        python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); \
b=p.chromium.launch(headless=False); ctx=b.new_context(); pg=ctx.new_page(); \
pg.goto('https://x.com/login'); input('Войдите в X и нажмите Enter...'); \
ctx.storage_state(path='twitter_state.json'); b.close(); p.stop()"

    Полученный ``twitter_state.json`` передаётся через ``storage_state_path``
    или переменную окружения ``TWITTER_STORAGE_STATE``.

    Возвращаемые элементы приведены к общему контракту ингест-слоя.
    """

    BASE_URL = "https://x.com"

    def __init__(
        self,
        targets: List[str],
        limit: int = 20,
        storage_state_path: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[Dict[str, Any]] = None,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        scroll_steps: int = 3,
        wait_timeout_ms: int = 20000,
        source_name: str = "twitter",
        **kwargs: Any,
    ) -> None:
        super().__init__(source_name=source_name, **kwargs)
        self.targets = [self._normalize_target(t) for t in targets]
        self.limit = limit
        self.storage_state_path = (
            storage_state_path or os.getenv("TWITTER_STORAGE_STATE")
        )
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent
        self.scroll_steps = scroll_steps
        self.wait_timeout_ms = wait_timeout_ms

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _normalize_target(target: str) -> str:
        target = target.strip().lstrip("@")
        target = re.sub(r"^https?://(?:x|twitter)\.com/", "", target, flags=re.IGNORECASE)
        return target.strip("/")

    @staticmethod
    def _first_line(text: str, max_len: int = 140) -> str:
        if not text:
            return ""
        first = re.split(r"[\n\r]+", text.strip(), maxsplit=1)[0]
        if len(first) > max_len:
            first = first[: max_len - 1].rstrip() + "…"
        return first

    @staticmethod
    def _is_logged_in(soup: BeautifulSoup) -> bool:
        # При незалогиненной сессии x.com показывает страницу входа/Sign in.
        if soup.find(attrs={"data-testid": "loginButton"}):
            return False
        return True

    # ------------------------------------------------------------- article parse
    def _parse_article(self, article, target: str) -> Optional[Dict[str, Any]]:
        text_node = article.select_one('[data-testid="tweetText"]')
        text = text_node.get_text(" ", strip=True) if text_node else ""
        if not text:
            return None  # пропускаем твиты без текста (медиа/ретвит без комментария)

        author = target
        user_block = article.select_one('[data-testid="User-Name"]')
        if user_block:
            # Ссылка на автора: /<username>/status/<id>
            user_link = user_block.select_one("a[href*='/status/']")
            if user_link:
                match = re.match(r"/([^/]+)/status/", user_link.get("href", ""))
                if match:
                    author = match.group(1)

        date = ""
        time_node = article.find("time")
        if time_node and time_node.has_attr("datetime"):
            date = time_node["datetime"]

        url = ""
        if user_link:
            href = user_link.get("href", "")
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

        return {
            "source": self.source_name,
            "author": author,
            "title": self._first_line(text),
            "text": text,
            "url": url or f"{self.BASE_URL}/{target}",
            "date": date,
            "target": target,
        }

    def _parse_html(self, html: str, target: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        if not self._is_logged_in(soup):
            raise RuntimeError(
                "Сессия X не авторизована. Передайте валидный storage_state "
                "(TWITTER_STORAGE_STATE) — см. docstring TwitterScraper."
            )

        results: List[Dict[str, Any]] = []
        seen_urls = set()
        for article in soup.select("article"):
            item = self._parse_article(article, target)
            if not item:
                continue
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)
            if len(results) >= self.limit:
                break
        return results

    # ------------------------------------------------------------------- driver
    def _sync_fetch(self) -> List[Dict[str, Any]]:
        from playwright.sync_api import sync_playwright  # отложенный импорт

        launch_kwargs: Dict[str, Any] = {"headless": self.headless}
        if self.proxy:
            launch_kwargs["proxy"] = {
                "server": self.proxy.get("server") or f"{self.proxy.get('scheme', 'http')}://"
                f"{self.proxy.get('host')}:{self.proxy.get('port')}",
            }

        results: List[Dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            context_kwargs: Dict[str, Any] = {
                "viewport": {"width": 1280, "height": 900},
                "user_agent": self.user_agent,
                "locale": "en-US",
            }
            if self.storage_state_path:
                context_kwargs["storage_state"] = self.storage_state_path
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            try:
                for target in self.targets:
                    try:
                        items = self._fetch_target(page, target)
                        results.extend(items)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[twitter] ошибка для {target}: {exc}")
                # Перезаписываем storage_state, чтобы освежать cookies между запусками.
                if self.storage_state_path:
                    context.storage_state(path=self.storage_state_path)
            finally:
                browser.close()
        return results

    def _fetch_target(self, page, target: str) -> List[Dict[str, Any]]:
        # Если таргет выглядит как поисковый запрос (есть пробел/хэштег как фраза),
        # используем URL поиска, иначе — страницу профиля.
        if " " in target or target.startswith("#") or target.startswith("search?q="):
            query = target if target.startswith("search?q=") else target
            url = f"{self.BASE_URL}/search?q={query.lstrip('#')}&f=live"
        else:
            url = f"{self.BASE_URL}/{target}"

        page.goto(url, wait_until="domcontentloaded", timeout=self.wait_timeout_ms)
        try:
            page.wait_for_selector("article", timeout=self.wait_timeout_ms)
        except Exception as exc:  # noqa: BLE001
            print(f"[twitter] статья не появилась для {target}: {exc}")

        # Подгружаем больше твитов прокруткой.
        for _ in range(self.scroll_steps):
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(1200)

        html = page.content()
        return self._parse_html(html, target)

    # ------------------------------------------------------------------- public
    async def fetch(self) -> Dict[str, Any]:
        items = await asyncio.to_thread(self._sync_fetch)
        return {"source": self.source_name, "items": items}
