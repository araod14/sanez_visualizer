import logging

import requests
import urllib3
from bs4 import BeautifulSoup

# BCV uses a Venezuelan government CA not in the standard trust store.
# We suppress the warning since we're only reading public data (no credentials sent).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

_BCV_URL = "https://www.bcv.org.ve/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-VE,es;q=0.9",
}


class ScraperError(Exception):
    pass


def _parse_rate(text: str) -> float:
    # BCV uses comma as decimal separator, e.g. "36,85142"
    return float(text.strip().replace(".", "").replace(",", "."))


def fetch_bcv_rates() -> dict[str, float]:
    """Return {"USD": <rate>, "EUR": <rate>} scraped from bcv.org.ve."""
    try:
        resp = requests.get(_BCV_URL, headers=_HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ScraperError(f"Error al conectar con BCV: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    rates: dict[str, float] = {}

    for currency, div_id in (("USD", "dolar"), ("EUR", "euro")):
        block = soup.find("div", id=div_id)
        if not block:
            raise ScraperError(f"No se encontró el bloque #{div_id} en la página de BCV")
        strong = block.find("strong")
        if not strong or not strong.text.strip():
            raise ScraperError(f"No se encontró el valor en #{div_id}")
        try:
            rates[currency] = _parse_rate(strong.text)
        except ValueError as e:
            raise ScraperError(f"No se pudo parsear la tasa de {currency}: {strong.text!r}") from e

    log.info("Tasas BCV obtenidas: %s", rates)
    return rates
