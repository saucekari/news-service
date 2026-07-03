import asyncio
import os
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from .base_ingester import BaseIngester


class TelegramClient(BaseIngester):
    """Парсер Telegram-каналов.

    Поддерживает два режима работы, выбираемых параметром ``mode``:

    * ``"telethon"`` — официальный MTProto-клиент через ``api_id``/``api_hash``.
      Даёт доступ к публичным и приватным каналам, требует авторизованную сессию.
    * ``"web"`` — парсинг публичных веб-превью ``https://t.me/s/<channel>``.
      Работает без токенов и авторизации, только для публичных каналов.
    * ``"auto"`` (по умолчанию) — выбирает ``telethon``, если заданы
      ``TELETHON_API_ID`` и ``TELETHON_API_HASH``, иначе откатывается на ``web``.

    Возвращаемые элементы приведены к общему контракту ингест-слоя:
    ``source``, ``author``, ``title``, ``text``, ``url``, ``date``.
    """

    def __init__(
        self,
        channels: List[str],
        mode: str = "auto",
        limit: int = 20,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session: Optional[str] = None,
        session_name: str = "news_sentiment_tg",
        proxy: Optional[Dict[str, Any]] = None,
        source_name: str = "telegram",
        **kwargs: Any,
    ) -> None:
        super().__init__(source_name=source_name, **kwargs)
        self.channels = [self._normalize_channel(c) for c in channels]
        self.limit = limit
        self.api_id = api_id or (int(os.getenv("TELETHON_API_ID")) if os.getenv("TELETHON_API_ID") else None)
        self.api_hash = api_hash or os.getenv("TELETHON_API_HASH")
        self.session = session or os.getenv("TELETHON_SESSION")
        self.session_name = session_name
        self.proxy = proxy

        self.mode = self._resolve_mode(mode)

        self.browser_impersonate = "chrome124"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _normalize_channel(channel: str) -> str:
        """Приводит @username / t.me/... / https://... к голому username."""
        channel = channel.strip().lstrip("@")
        channel = re.sub(r"^https?://t\.me/", "", channel, flags=re.IGNORECASE)
        channel = re.sub(r"^https?://telegram\.me/", "", channel, flags=re.IGNORECASE)
        channel = re.sub(r"^t\.me/", "", channel, flags=re.IGNORECASE)
        return channel.strip("/")

    def _resolve_mode(self, mode: str) -> str:
        if mode not in ("auto", "telethon", "web"):
            raise ValueError(f"Неизвестный режим Telegram: {mode!r} (ожидаются auto/telethon/web)")
        if mode == "auto":
            return "telethon" if (self.api_id and self.api_hash) else "web"
        return mode

    @staticmethod
    def _first_line(text: str, max_len: int = 140) -> str:
        """Из длинного текста сообщения формирует короткий заголовок."""
        if not text:
            return ""
        first = re.split(r"[\n\r]+", text.strip(), maxsplit=1)[0]
        if len(first) > max_len:
            first = first[: max_len - 1].rstrip() + "…"
        return first

    # --------------------------------------------------------------- web preview
    def _sync_fetch_web(self) -> List[Dict[str, Any]]:
        """Синхронный парсинг публичных превью t.me/s/<channel> через curl_cffi."""
        results: List[Dict[str, Any]] = []
        for channel in self.channels:
            try:
                url = f"https://t.me/s/{channel}"
                response = curl_requests.get(
                    url,
                    headers=self.headers,
                    impersonate=self.browser_impersonate,
                    timeout=15,
                )
                if response.status_code != 200:
                    print(f"[telegram:web] {channel}: статус {response.status_code}")
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                wraps = soup.select(".tgme_widget_message_wrap")

                # Превью отдают последние ~20 сообщений; оставляем нужный лимит.
                for wrap in wraps[-self.limit :] if self.limit else wraps:
                    item = self._parse_web_message(wrap, channel)
                    if item:
                        results.append(item)
            except Exception as exc:  # noqa: BLE001 — логируем и идём дальше
                print(f"[telegram:web] ошибка для {channel}: {exc}")
        return results

    def _parse_web_message(self, wrap, channel: str) -> Optional[Dict[str, Any]]:
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text(" ", strip=True) if text_node else ""
        if not text:
            return None  # пропускаем служебные сообщения без текста (фото/видео-посты и т.п.)

        author_node = wrap.select_one(".tgme_widget_message_owner_name") or wrap.select_one(
            ".tgme_widget_message_from"
        )
        author = author_node.get_text(" ", strip=True) if author_node else channel

        time_node = wrap.select_one("time.datetime, time[datetime]")
        date = ""
        if time_node and time_node.has_attr("datetime"):
            date = time_node["datetime"]
        elif time_node:
            date = time_node.get_text(strip=True)

        post_id = wrap.get("data-post")
        if not post_id:
            inner = wrap.select_one(".tgme_widget_message")
            post_id = inner.get("data-post") if inner else None
        link = f"https://t.me/{post_id}" if post_id else f"https://t.me/s/{channel}"

        return {
            "source": self.source_name,
            "author": author,
            "title": self._first_line(text),
            "text": text,
            "url": link,
            "date": date,
            "channel": channel,
        }

    # --------------------------------------------------------------- telethon
    def _sync_fetch_telethon(self) -> List[Dict[str, Any]]:
        """Синхронный сбор сообщений через Telethon (MTProto)."""
        try:
            from telethon import TelegramClient as _TgClient  # отложенный импорт
            from telethon.sessions import StringSession
        except ImportError as exc:  # pragma: no cover - зависит от окружения
            raise RuntimeError(
                "Для режима telethon установите библиотеку: pip install telethon"
            ) from exc

        if not (self.api_id and self.api_hash):
            raise RuntimeError(
                "Режим telethon требует TELETHON_API_ID и TELETHON_API_HASH "
                "(получите на https://my.telegram.org)."
            )

        session_arg = StringSession(self.session) if self.session else self.session_name
        client_kwargs: Dict[str, Any] = {}
        if self.proxy:
            client_kwargs["proxy"] = tuple(self.proxy.get(k) for k in ("socks",)) if self.proxy.get("socks") else (
                self.proxy.get("host"),
                int(self.proxy.get("port", 0)),
            )

        results: List[Dict[str, Any]] = []
        client = _TgClient(self.api_id, self.api_hash, session_arg, **client_kwargs)
        try:
            client.start()
            for channel in self.channels:
                try:
                    entity = client.get_entity(channel)
                    for message in client.iter_messages(entity, limit=self.limit):
                        item = self._parse_telethon_message(message, channel)
                        if item:
                            results.append(item)
                except Exception as exc:  # noqa: BLE001
                    print(f"[telegram:telethon] ошибка для {channel}: {exc}")
        finally:
            client.disconnect()
        return results

    def _parse_telethon_message(self, message, channel: str) -> Optional[Dict[str, Any]]:
        text = getattr(message, "message", None) or getattr(message, "text", None) or ""
        if not text:
            return None

        sender = getattr(message, "sender", None)
        author = ""
        if sender is not None:
            author = (
                getattr(sender, "username", None)
                or getattr(sender, "title", None)
                or getattr(sender, "first_name", None)
                or str(getattr(sender, "id", channel))
            )

        date = ""
        if getattr(message, "date", None) is not None:
            date = message.date.isoformat()

        msg_id = getattr(message, "id", None)
        link = f"https://t.me/{channel}/{msg_id}" if msg_id else f"https://t.me/{channel}"

        return {
            "source": self.source_name,
            "author": author or channel,
            "title": self._first_line(text),
            "text": text,
            "url": link,
            "date": date,
            "channel": channel,
        }

    # ------------------------------------------------------------------- public
    async def fetch(self) -> Dict[str, Any]:
        if self.mode == "telethon":
            items = await asyncio.to_thread(self._sync_fetch_telethon)
        else:
            items = await asyncio.to_thread(self._sync_fetch_web)
        return {"source": self.source_name, "items": items}
