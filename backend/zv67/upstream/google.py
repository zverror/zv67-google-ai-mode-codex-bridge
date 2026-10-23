"""Google AI Mode provider using a real Chrome browser over CDP.

The implementation follows the public protocol description, not copied source.
Each account gets an isolated temporary browser profile.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from zv67.domain import CapabilityStatus, ModelDescriptor, NormalizedRequest
from zv67.upstream.base import (
    ProviderError,
    ProviderErrorKind,
    ProviderHealth,
    UpstreamProvider,
    UpstreamResult,
)

GOOGLE_MODEL_ID = "google-ai-mode"
HOST = "https://www.google.com"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise ProviderError(
        ProviderErrorKind.UNAVAILABLE, "Google Chrome was not found"
    )


def _playwright_cookies(cookies: list[dict]) -> list[dict]:
    result: list[dict] = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        expires = cookie.get("expirationDate")
        same_site = str(cookie.get("sameSite", "lax")).lower()
        mapping = {
            "no_restriction": "None",
            "unspecified": "Lax",
            "lax": "Lax",
            "strict": "Strict",
        }
        result.append(
            {
                "name": name,
                "value": value,
                "domain": cookie.get("domain") or ".google.com",
                "path": cookie.get("path") or "/",
                "expires": float(expires) if expires else -1,
                "httpOnly": bool(cookie.get("httpOnly", False)),
                "secure": bool(cookie.get("secure", False)),
                "sameSite": mapping.get(same_site, "Lax"),
            }
        )
    return result


def _attr(document: str, name: str) -> str | None:
    match = re.search(
        rf"data-{re.escape(name)}\s*=\s*[\"']([^\"']*)[\"']", document
    )
    return html_lib.unescape(match.group(1)) if match else None


@dataclass(frozen=True)
class ThreadState:
    mstk: str | None = None
    thread_id: str | None = None
    elrc: str | None = None
    stkp: str | None = None
    xsrf: str | None = None
    ei: str | None = None


def _state_from(document: str, previous: ThreadState | None = None) -> ThreadState:
    previous = previous or ThreadState()
    return ThreadState(
        mstk=_attr(document, "mstk") or previous.mstk,
        thread_id=_attr(document, "session-thread-id") or previous.thread_id,
        elrc=_attr(document, "elrc")
        or _attr(document, "ce-elrc")
        or previous.elrc,
        stkp=_attr(document, "stkp") or previous.stkp,
        xsrf=_attr(document, "xsrf-folif-token") or previous.xsrf,
        ei=_attr(document, "ei") or previous.ei,
    )


_SKIP_PREFIXES = (
    "AI Mode reply for",
    "Ответ в режиме ИИ, исходный запрос:",
    "Shared",
    "Copy",
    "Скопировано",
    "Не удалось скопировать",
    "Эта ссылка позволяет",
    "При передаче ссылки",
    "Копировать ссылку",
    "Good response",
    "Show more",
    "Follow up",
    "Sources",
)

_SKIP_EXACT = {
    "0 files",
    "0 файлов",
    "Общее",
    "Показать все",
    "Свернуть",
    "Копировать",
    "Поделиться",
    "Поделиться ссылкой",
    "Хороший ответ",
    "Плохой ответ",
    "Дополнительно",
    "Об этом ответе",
    "Facebook",
    "Gmail",
    "Reddit",
    "WhatsApp",
    "X",
}


def _clean_text(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.select(
        "div.IQTBxd, div.eFSEae, div.DBd2Wb, div.zkL70c, span.WBgIic, button"
    ):
        tag.decompose()

    thread = soup.find(attrs={"data-session-thread-id": True})
    container = thread.parent if thread is not None and thread.parent else soup
    blocks: list[str] = []
    for child in container.find_all(recursive=False):
        classes = set(child.get("class") or [])
        if classes & {"CKgc1d", "IQTBxd", "DBd2Wb", "zkL70c", "vIWmYe"}:
            continue
        if child.name in ("ul", "ol"):
            for item in child.find_all("li", recursive=False):
                text = re.sub(r"\s+", " ", item.get_text(" ", strip=True)).strip()
                if text:
                    blocks.append("- " + text)
            continue
        heading = child.find(["h1", "h2", "h3", "h4"])
        text = re.sub(r"\s+", " ", child.get_text(" ", strip=True)).strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in _SKIP_PREFIXES):
            continue
        if text in _SKIP_EXACT or text in {"+1", "+2", "+3", "+4", "+5"}:
            continue
        if re.fullmatch(r"(Общее|Shared)\s+0\s+(файлов|files)", text):
            continue
        if text in {"Развернуть карту", "Увеличить", "Уменьшить"}:
            continue
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        if heading is not None and heading in child.find_all(["h1", "h2", "h3", "h4"], limit=1):
            blocks.append("## " + text)
        else:
            blocks.append(text)
    return "\n\n".join(blocks)


class GoogleBrowserSession:
    def __init__(
        self,
        account_id: str,
        cookies: list[dict],
        timeout: int = 60,
        *,
        headless: bool = True,
    ) -> None:
        self.account_id = account_id
        self._cookies = cookies
        self._timeout = timeout
        self._headless = headless
        self._process: subprocess.Popen | None = None
        self._profile: Path | None = None
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        chrome = _find_chrome()
        port = _free_port()
        self._profile = Path(tempfile.mkdtemp(prefix="zv67-chrome-"))
        flags = [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={self._profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=ru-RU",
            "--disable-blink-features=AutomationControlled",
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        ]
        if self._headless:
            flags += ["--headless=new", "--window-size=1280,900"]
        else:
            flags += ["--window-size=900,700", "--window-position=-2400,-2400"]
        flags.append("about:blank")
        self._process = subprocess.Popen(
            flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await self._wait_for_cdp(port)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}"
        )
        self._context = (
            self._browser.contexts[0]
            if self._browser.contexts
            else await self._browser.new_context()
        )
        try:
            await self._context.add_cookies(_playwright_cookies(self._cookies))
        except Exception as exc:
            raise ProviderError(
                ProviderErrorKind.UNAUTHORIZED,
                "Google rejected the stored cookies",
            ) from exc
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._timeout * 1000)
        await self._page.goto(HOST + "/", wait_until="domcontentloaded", timeout=self._timeout * 1000)
        await asyncio.sleep(1.2)
        self._started = True

    async def _wait_for_cdp(self, port: int) -> None:
        deadline = time.monotonic() + 20
        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get(
                        f"http://127.0.0.1:{port}/json/version", timeout=2
                    )
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.2)
        raise ProviderError(
            ProviderErrorKind.UNAVAILABLE, "Chrome did not start its CDP endpoint"
        )

    async def chat(self, query: str, state: ThreadState | None) -> tuple[str, ThreadState]:
        await self.start()
        if state and state.mstk:
            try:
                fragment = await self._folif(query, state, followup=True)
                text, new_state = self._parse_fragment(fragment, state)
                if text:
                    return text, new_state
            except Exception:
                pass
        await self._search_page(query)
        document = await self._page.content()
        state0 = _state_from(document)
        if not (state0.xsrf and state0.stkp and state0.elrc and state0.ei):
            raise self._classify_page(document, self._page.url)
        fragment = await self._folif(query, state0, followup=False)
        text, new_state = self._parse_fragment(fragment, state0)
        if not text:
            raise ProviderError(
                ProviderErrorKind.UNAVAILABLE, "AI Mode returned an empty answer"
            )
        return text, new_state

    async def _search_page(self, query: str) -> None:
        assert self._page is not None
        url = HOST + "/search?" + urlencode({"q": query, "udm": "50", "hl": "ru"})
        response = await self._page.goto(
            url, wait_until="domcontentloaded", timeout=self._timeout * 1000
        )
        if response is None:
            raise ProviderError(ProviderErrorKind.UNAVAILABLE, "search page did not load")
        if "/sorry/" in self._page.url:
            raise ProviderError(
                ProviderErrorKind.RATE_LIMITED, "Google requires verification for this session"
            )
        await asyncio.sleep(0.4)

    async def _folif(self, query: str, state: ThreadState, *, followup: bool) -> str:
        assert self._page is not None
        params = (
            f"ei={quote(state.ei or '')}&yv=3&udm=50&hl=ru"
            f"&stkp={quote(state.stkp or '')}&cs=0&csuir=0"
            f"&elrc={quote(state.elrc or '')}&q={quote(query)}"
        )
        if followup and state.mstk:
            params += f"&mstk={quote(state.mstk)}&csui=3"
        params += f"&async=_fmt:adl,_xsrf:{quote(state.xsrf or '')}"
        url = HOST + "/async/folif?" + params
        result = await self._page.evaluate(
            """async (url) => {
                const r = await fetch(url, {credentials: 'include'});
                return {status: r.status, url: r.url, text: await r.text()};
            }""",
            url,
        )
        if result["status"] in (401, 403):
            raise ProviderError(
                ProviderErrorKind.UNAUTHORIZED, "Google rejected the AI Mode request"
            )
        if result["status"] != 200:
            raise ProviderError(
                ProviderErrorKind.UNAVAILABLE,
                f"AI Mode returned HTTP {result['status']}",
            )
        return str(result["text"])

    @staticmethod
    def _parse_fragment(
        fragment: str, previous: ThreadState
    ) -> tuple[str, ThreadState]:
        text = _clean_text(fragment)
        state = _state_from(fragment, previous)
        return text, state

    @staticmethod
    def _classify_page(document: str, url: str) -> ProviderError:
        if "/sorry/" in url or "unusual traffic" in document.lower():
            return ProviderError(
                ProviderErrorKind.RATE_LIMITED,
                "Google blocked the session with a verification page",
            )
        if "SG_REL" in document:
            return ProviderError(
                ProviderErrorKind.UNAVAILABLE,
                "Google soft-blocked the browser session",
            )
        if "Sign in" in document and "data-xsrf-folif-token" not in document:
            return ProviderError(
                ProviderErrorKind.UNAUTHORIZED,
                "Google session is not authenticated; re-import cookies",
            )
        return ProviderError(
            ProviderErrorKind.UNAVAILABLE,
            "AI Mode bootstrap tokens are missing",
        )

    async def close(self) -> None:
        self._started = False
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        if self._process is not None:
            self._process.terminate()
            try:
                await asyncio.to_thread(self._process.wait, 10)
            except Exception:
                self._process.kill()
            self._process = None
        if self._profile is not None:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._profile = None


class GoogleAIModeProvider(UpstreamProvider):
    provider_id = "google"

    def __init__(
        self,
        credentials_loader: Callable[[str], dict],
        *,
        max_sessions: int = 2,
        timeout: int = 60,
        headless: bool = True,
        models: list[ModelDescriptor] | None = None,
    ) -> None:
        self._load_credentials = credentials_loader
        self._max_sessions = max_sessions
        self._timeout = timeout
        self._headless = headless
        self._sessions: OrderedDict[str, GoogleBrowserSession] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._threads: OrderedDict[tuple[str, str], ThreadState] = OrderedDict()
        self._models = models or [
            ModelDescriptor(
                id=GOOGLE_MODEL_ID,
                display_name="Google AI Mode (real)",
                provider="ZV67",
                upstream="google",
                capabilities={
                    "chat": CapabilityStatus.VERIFIED,
                    "streaming": CapabilityStatus.VERIFIED,
                    "responses": CapabilityStatus.VERIFIED,
                    "tool_calling": CapabilityStatus.UNSUPPORTED,
                    "session_persistence": CapabilityStatus.VERIFIED,
                    "images": CapabilityStatus.UNSUPPORTED,
                },
            )
        ]

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ok",
            provider=self.provider_id,
            detail="Chrome CDP launcher ready",
        )

    async def list_models(self) -> list[ModelDescriptor]:
        return list(self._models)

    async def complete(self, request: NormalizedRequest) -> UpstreamResult:
        if request.model_id != GOOGLE_MODEL_ID:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                f"model '{request.model_id}' is not served by Google AI Mode",
            )
        if not request.account_id:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                "Google AI Mode requires a selected account",
            )
        query = request.last_user_text
        if not query:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST, "a user message is required"
            )
        account_id = request.account_id
        lock = self._locks.setdefault(account_id, asyncio.Lock())
        async with lock:
            thread_key = (account_id, request.session_id or request.request_id)
            state = self._threads.get(thread_key)
            last_error: Exception | None = None
            for attempt in range(2):
                session = await self._session(account_id)
                try:
                    text, new_state = await asyncio.wait_for(
                        session.chat(query, state),
                        timeout=self._timeout + 20,
                    )
                except asyncio.TimeoutError as exc:
                    await self._drop_session(account_id)
                    last_error = ProviderError(
                        ProviderErrorKind.TIMEOUT,
                        "Google AI Mode browser session timed out",
                    )
                    if attempt == 0:
                        state = None
                        continue
                    raise last_error from exc
                except ProviderError as exc:
                    last_error = exc
                    if attempt == 0 and exc.kind in (
                        ProviderErrorKind.UNAVAILABLE,
                        ProviderErrorKind.TIMEOUT,
                    ):
                        await self._drop_session(account_id)
                        state = None
                        continue
                    raise
                except Exception as exc:
                    await self._drop_session(account_id)
                    raise ProviderError(
                        ProviderErrorKind.UNAVAILABLE,
                        "Google AI Mode browser session failed",
                    ) from exc
                self._threads[thread_key] = new_state
                self._threads.move_to_end(thread_key)
                while len(self._threads) > 64:
                    self._threads.popitem(last=False)
                return UpstreamResult(
                    text=text,
                    model_id=request.model_id,
                    upstream_session_id=new_state.thread_id,
                )
            raise last_error or ProviderError(
                ProviderErrorKind.UNAVAILABLE, "Google AI Mode failed"
            )

    async def _session(self, account_id: str) -> GoogleBrowserSession:
        session = self._sessions.get(account_id)
        if session is not None:
            self._sessions.move_to_end(account_id)
            return session
        while len(self._sessions) >= self._max_sessions:
            _, stale = self._sessions.popitem(last=False)
            await stale.close()
        credentials = await asyncio.to_thread(self._load_credentials, account_id)
        cookies = credentials.get("cookies") if credentials else None
        if not cookies:
            raise ProviderError(
                ProviderErrorKind.UNAUTHORIZED,
                "account has no imported cookies",
            )
        session = GoogleBrowserSession(
            account_id,
            cookies,
            timeout=self._timeout,
            headless=self._headless,
        )
        self._sessions[account_id] = session
        return session

    async def _drop_session(self, account_id: str) -> None:
        session = self._sessions.pop(account_id, None)
        if session is not None:
            await session.close()

    async def aclose(self) -> None:
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for session in sessions:
            await session.close()

