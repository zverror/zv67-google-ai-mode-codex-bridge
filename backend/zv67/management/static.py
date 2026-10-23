"""Serve the built dashboard or a setup page when the build is absent."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

router = APIRouter()

DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"

SETUP_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>ZV67</title>
<style>body{font-family:system-ui;background:#0b1020;color:#e8ecf8;display:grid;place-items:center;height:100vh;margin:0}
main{max-width:620px;padding:32px;border:1px solid #2a3557;border-radius:16px;background:#121a33}
code{background:#0b1020;padding:2px 6px;border-radius:6px}</style></head>
<body><main><h1>ZV67</h1><p>Панель управления ещё не собрана.</p>
<p>Соберите frontend командой <code>npm run build</code> в каталоге <code>frontend</code>.</p>
<p>API доступен по адресу <code>/admin/api</code>.</p></main></body></html>"""


@router.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse("/admin/")


@router.get("/admin")
async def admin_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/")


@router.get("/admin/{path:path}")
async def admin_spa(path: str, request: Request):
    if path.startswith("api/"):
        return HTMLResponse("Not found", status_code=404)
    if DIST.exists():
        candidate = (DIST / path).resolve()
        try:
            candidate.relative_to(DIST.resolve())
        except ValueError:
            return HTMLResponse("Not found", status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
    return HTMLResponse(SETUP_PAGE)

