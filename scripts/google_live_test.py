#!/usr/bin/env python3
"""Live probe for Google AI Mode using stored account cookies.

This is a diagnostic script. It never prints cookie values.
"""

from __future__ import annotations

import argparse
import asyncio
import html as html_lib
import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy import select

from zv67.persistence.db import Database
from zv67.persistence.models import Account
from zv67.security.credentials import CredentialService
from zv67.security.crypto import FileMasterKeyStore, SecretBox

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HOST = "https://www.google.com"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def load_cookies(account_name: str) -> list[dict]:
    data = Path.home() / "Library" / "Application Support" / "ZV67"
    database = Database(data / "zv67.sqlite3")
    box = SecretBox(FileMasterKeyStore(data / "master.key").get_or_create())
    service = CredentialService(box)
    try:
        with database.session() as session:
            account = session.scalar(
                select(Account).where(Account.display_name == account_name)
            )
            if account is None:
                raise SystemExit(f"account '{account_name}' not found")
            payload = service.load(session, account.id)
    finally:
        database.close()
    if not payload or not payload.get("cookies"):
        raise SystemExit(f"account '{account_name}' has no cookies")
    return payload["cookies"]


def playwright_cookies(cookies: list[dict]) -> list[dict]:
    result = []
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


def attr(document: str, name: str) -> str | None:
    match = re.search(rf'data-{re.escape(name)}="([^"]*)"', document)
    return html_lib.unescape(match.group(1)) if match else None


async def wait_for_cdp(port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"http://127.0.0.1:{port}/json/version")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError("Chrome CDP endpoint did not start")


async def run(account: str, query: str, headed: bool = False, arv: str | None = None) -> None:
    cookies = load_cookies(account)
    port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="zv67-chrome-"))
    flags = [
        CHROME,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--lang=en-US",
        "--disable-blink-features=AutomationControlled",
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    ]
    if headed:
        flags += ["--window-size=900,700", "--window-position=-2400,-2400"]
    else:
        flags += ["--headless=new", "--window-size=1280,900"]
    flags.append("about:blank")
    process = subprocess.Popen(
        flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        await wait_for_cdp(port)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}"
            )
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            await context.add_cookies(playwright_cookies(cookies))
            page = await context.new_page()
            await page.goto(HOST + "/", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(1.5)
            search_params = {"q": query, "udm": "50", "hl": "en"}
            if arv:
                search_params["arv"] = arv
            search_url = HOST + "/search?" + urlencode(search_params)
            response = await page.goto(
                search_url, wait_until="domcontentloaded", timeout=45000
            )
            document = await page.content()
            print(
                json.dumps(
                    {
                        "search_status": response.status if response else None,
                        "page_len": len(document),
                        "url": page.url,
                        "sg_rel": "SG_REL" in document,
                        "sorry": "/sorry/" in page.url,
                        "xsrf": bool(attr(document, "xsrf-folif-token")),
                        "stkp": bool(attr(document, "stkp")),
                        "elrc": bool(attr(document, "elrc") or attr(document, "ce-elrc")),
                        "ei": bool(attr(document, "ei")),
                    },
                    ensure_ascii=False,
                )
            )
            xsrf = attr(document, "xsrf-folif-token")
            stkp = attr(document, "stkp")
            elrc = attr(document, "elrc") or attr(document, "ce-elrc")
            ei = attr(document, "ei")
            if not (xsrf and stkp and elrc and ei):
                Path("/tmp/zv67_search.html").write_text(document, encoding="utf-8")
                print("tokens missing; page saved to /tmp/zv67_search.html")
                return
            params = (
                f"ei={quote(ei)}&yv=3&udm=50&hl=en&stkp={quote(stkp)}"
                f"&cs=0&csuir=0&elrc={quote(elrc)}&q={quote(query)}"
            )
            if arv:
                params += f"&arv={quote(arv)}"
            params += f"&async=_fmt:adl,_xsrf:{quote(xsrf)}"
            folif_url = HOST + "/async/folif?" + params
            result = await page.evaluate(
                """async (url) => {
                    const r = await fetch(url, {credentials: 'include'});
                    return {status: r.status, url: r.url, text: await r.text()};
                }""",
                folif_url,
            )
            fragment = result["text"]
            Path("/tmp/zv67_folif.html").write_text(fragment, encoding="utf-8")
            soup = BeautifulSoup(fragment, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = "\n".join(
                line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
            )
            print(
                json.dumps(
                    {
                        "folif_status": result["status"],
                        "fragment_len": len(fragment),
                        "mstk": bool(attr(fragment, "mstk")),
                        "thread_id": bool(attr(fragment, "session-thread-id")),
                        "text_len": len(text),
                        "arv": arv,
                        "flash_marker": "3.8 Flash" in fragment,
                        "argon_marker": "Argon" in fragment,
                    },
                    ensure_ascii=False,
                )
            )
            print("--- answer preview ---")
            print(text[:1200])
            await browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="AI")
    parser.add_argument("--query", default="Что такое искусственный интеллект?")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--arv", choices=["2", "3"], default=None)
    args = parser.parse_args()
    asyncio.run(run(args.account, args.query, headed=args.headed, arv=args.arv))

