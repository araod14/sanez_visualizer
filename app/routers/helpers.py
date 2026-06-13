"""Helpers HTTP compartidos por los routers."""

from urllib.parse import urlencode

from fastapi.responses import RedirectResponse


def back_to(url: str, *, ok: str = "", error: str = "") -> RedirectResponse:
    qs = urlencode({k: v for k, v in {"ok": ok, "error": error}.items() if v})
    sep = "&" if "?" in url else "?"
    return RedirectResponse(url=f"{url}{sep}{qs}" if qs else url, status_code=302)
