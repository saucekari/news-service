import sys
import os
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.ingest.telegram_client import TelegramClient  # noqa: E402
from src.ingest.twitter_scraper import TwitterScraper  # noqa: E402


# ----------------------------------------------------------------------- Telegram
TG_WEB_HTML = """
<html><body>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="newschannel/42">
      <div class="tgme_widget_message_owner_name">News Channel</div>
      <div class="tgme_widget_message_text">BTC breaks 100k, $BTC rally continues. Bullish.</div>
      <time datetime="2024-01-01T12:00:00+00:00">Jan 1</time>
    </div>
  </div>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="newschannel/43">
      <div class="tgme_widget_message_owner_name">News Channel</div>
      <div class="tgme_widget_message_text">Second message about ETH.</div>
      <time datetime="2024-01-01T13:00:00+00:00">Jan 1</time>
    </div>
  </div>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="newschannel/44">
      <!-- сообщение без текста — должно отфильтроваться -->
      <div class="tgme_widget_message_owner_name">News Channel</div>
    </div>
  </div>
</body></html>
"""


def test_telegram_normalize_channel():
    assert TelegramClient._normalize_channel("@durov") == "durov"
    assert TelegramClient._normalize_channel("https://t.me/durov") == "durov"
    assert TelegramClient._normalize_channel("t.me/durov/") == "durov"


def test_telegram_mode_auto_without_creds_chooses_web(monkeypatch):
    monkeypatch.delenv("TELETHON_API_ID", raising=False)
    monkeypatch.delenv("TELETHON_API_HASH", raising=False)
    client = TelegramClient(channels=["test"], mode="auto")
    assert client.mode == "web"


def test_telegram_mode_auto_with_creds_chooses_telethon():
    client = TelegramClient(
        channels=["test"], mode="auto", api_id=123, api_hash="hash"
    )
    assert client.mode == "telethon"


def test_telegram_web_parse_fields():
    client = TelegramClient(channels=["newschannel"], mode="web")
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(TG_WEB_HTML, "html.parser")
    wraps = soup.select(".tgme_widget_message_wrap")
    items = [client._parse_web_message(w, "newschannel") for w in wraps]
    items = [i for i in items if i]

    assert len(items) == 2  # третье сообщение без текста отфильтровано
    first = items[0]
    assert first["source"] == "telegram"
    assert first["author"] == "News Channel"
    assert "BTC" in first["text"]
    assert first["url"] == "https://t.me/newschannel/42"
    assert first["date"] == "2024-01-01T12:00:00+00:00"
    assert first["title"]  # короткий заголовок не пустой


def test_telegram_web_fetch_via_mock(monkeypatch):
    client = TelegramClient(channels=["newschannel"], mode="web", limit=10)

    captured = {"called": False}

    def fake_get(url, **kwargs):
        captured["called"] = True
        return SimpleNamespace(status_code=200, content=TG_WEB_HTML.encode())

    monkeypatch.setattr("src.ingest.telegram_client.curl_requests.get", fake_get)

    result = client._sync_fetch_web()
    assert captured["called"]
    assert len(result) == 2
    assert result[0]["channel"] == "newschannel"


async def test_telegram_fetch_returns_contract(monkeypatch):
    client = TelegramClient(channels=["newschannel"], mode="web")

    monkeypatch.setattr(
        "src.ingest.telegram_client.curl_requests.get",
        lambda *a, **k: SimpleNamespace(status_code=200, content=TG_WEB_HTML.encode()),
    )

    data = await client.fetch()
    assert data["source"] == "telegram"
    assert isinstance(data["items"], list)
    # Контракт данных для analyze-слоя:
    for item in data["items"]:
        assert all(k in item for k in ("source", "author", "title", "text", "url", "date"))


def test_telegram_telethon_mode_requires_creds():
    client = TelegramClient(channels=["test"], mode="telethon")
    with pytest.raises(RuntimeError, match="TELETHON_API_ID"):
        client._sync_fetch_telethon()


# ----------------------------------------------------------------------- Twitter/X
X_HTML = """
<html><body>
  <article>
    <div data-testid="tweetText">Just bought more $BTC, feeling bullish about the pump.</div>
    <div data-testid="User-Name">
      <a href="/cryptofan/status/111">cryptofan · 2h</a>
    </div>
    <time datetime="2024-01-01T10:00:00.000Z">Jan 1</time>
  </article>
  <article>
    <div data-testid="tweetText">$ETH to the moon 🚀 long position ready.</div>
    <div data-testid="User-Name">
      <a href="/whale/status/222">whale · 1h</a>
    </div>
    <time datetime="2024-01-01T11:00:00.000Z">Jan 1</time>
  </article>
  <article>
    <!-- ретвит медиа без текста — отфильтровывается -->
    <div data-testid="User-Name"><a href="/media/status/333">media</a></div>
  </article>
</body></html>
"""

X_LOGIN_HTML = """
<html><body>
  <div data-testid="loginButton">Sign in</div>
</body></html>
"""


def test_twitter_normalize_target():
    assert TwitterScraper._normalize_target("@elonmusk") == "elonmusk"
    assert TwitterScraper._normalize_target("https://x.com/elonmusk") == "elonmusk"
    assert TwitterScraper._normalize_target("https://twitter.com/elonmusk/") == "elonmusk"


def test_twitter_parse_html_logged_out_raises():
    scraper = TwitterScraper(targets=["cryptofan"], storage_state_path="state.json")
    with pytest.raises(RuntimeError, match="авторизована"):
        scraper._parse_html(X_LOGIN_HTML, "cryptofan")


def test_twitter_parse_articles_fields():
    scraper = TwitterScraper(targets=["cryptofan"], limit=5)
    items = scraper._parse_html(X_HTML, "cryptofan")

    assert len(items) == 2  # медиа-твит без текста отфильтрован
    first = items[0]
    assert first["source"] == "twitter"
    assert first["author"] == "cryptofan"
    assert "$BTC" in first["text"]
    assert first["url"] == "https://x.com/cryptofan/status/111"
    assert first["date"] == "2024-01-01T10:00:00.000Z"


def test_twitter_parse_respects_limit():
    scraper = TwitterScraper(targets=["cryptofan"], limit=1)
    items = scraper._parse_html(X_HTML, "cryptofan")
    assert len(items) == 1


def test_twitter_parse_deduplicates_urls():
    # Если один и тот же твит встретится дважды (после скролла) — не дублируем.
    dedup_html = X_HTML + X_HTML
    scraper = TwitterScraper(targets=["cryptofan"], limit=10)
    items = scraper._parse_html(dedup_html, "cryptofan")
    urls = [i["url"] for i in items]
    assert len(urls) == len(set(urls))
