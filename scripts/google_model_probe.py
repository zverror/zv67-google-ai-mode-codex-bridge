#!/usr/bin/env python3
"""Inspect how Google AI Mode carries its model selection."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from google_live_test import load_cookies, playwright_cookies
from playwright.async_api import async_playwright

from zv67.upstream.google import GoogleBrowserSession


async def main() -> None:
    cookies = load_cookies("AI")
    session = GoogleBrowserSession("AI", cookies, headless=True)
    await session.start()
    page = session._page
    assert page is not None
    requests: list[str] = []
    page.on(
        "request",
        lambda request: requests.append(request.url)
        if any(key in request.url for key in ("/search", "/async/folif", "batchexecute"))
        else None,
    )
    await page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(1)
    html = await page.content()
    Path("/tmp/zv67_home.html").write_text(html, encoding="utf-8")
    positions = {
        phrase: [match.start() for match in re.finditer(re.escape(phrase), html)][:3]
        for phrase in ("3.8 Flash", "Argon", "Auto", "aim", "model")
    }
    print(json.dumps({"len": len(html), "positions": positions}, ensure_ascii=False))
    for phrase in ("3.8 Flash", "Argon"):
        for index in positions[phrase][:2]:
            print("---", phrase)
            print(html[max(0, index - 400) : index + 400].replace("\n", " ")[:800])
    buttons = await page.locator("button").all()
    labels = []
    for button in buttons[:60]:
        try:
            label = (await button.get_attribute("aria-label")) or ""
            text = (await button.inner_text())[:40]
        except Exception:
            continue
        if label or text:
            labels.append({"aria": label[:80], "text": text.strip()})
    print(json.dumps(labels, ensure_ascii=False)[:4000])
    print("cookies", [c["name"] for c in await page.context.cookies() if "AIM" in c["name"] or "MODEL" in c["name"].upper()])
    print("localStorage", await page.evaluate("Object.keys(localStorage)"))
    print("requests", requests[:20])
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())

