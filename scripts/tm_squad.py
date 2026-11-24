"""
Transfermarkt.be squad scraper (SeleniumBase CDP mode).

Haalt de kaderpagina van één club op en schrijft naam, positie, leeftijd en
marktwaarde naar CSV. Bedoeld voor kleine, trage runs, niet voor bulk.

Installatie:
    pip install seleniumbase beautifulsoup4

Gebruik:
    python tm_squad.py "https://www.transfermarkt.be/sv-zulte-waregem/kader/verein/3752/saison_id/2025"
"""
import csv
import hashlib
import random
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from seleniumbase import SB

CACHE = Path("cache")
CACHE.mkdir(exist_ok=True)


def is_blocked(html: str) -> bool:
    """Herken de AWS WAF challenge/captcha pagina."""
    low = html.lower()
    return "awswaf" in low or "aws-waf" in low or ("captcha" in low and "table class=\"items\"" not in low)


def fetch_html(sb, url: str) -> str:
    # Cache: dezelfde pagina nooit twee keer ophalen
    key = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".html")
    if key.exists():
        return key.read_text(encoding="utf-8")

    sb.activate_cdp_mode(url)
    sb.sleep(random.uniform(3, 5))

    html = sb.cdp.get_page_source()
    if is_blocked(html):
        print("Challenge gedetecteerd, probeer solve_captcha()...")
        try:
            sb.solve_captcha()          # werkt voor checkbox-achtige captchas
        except Exception as e:
            print("solve_captcha faalde:", e)
        sb.sleep(random.uniform(4, 6))
        html = sb.cdp.get_page_source()

    if is_blocked(html):
        raise RuntimeError(
            "Nog steeds geblokkeerd. Los de puzzel handmatig op in het "
            "venster (je hebt 60s) of probeer een ander IP / --use-chromium."
        )

    key.write_text(html, encoding="utf-8")
    return html


def parse_squad(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.items > tbody > tr")
    players = []
    for tr in rows:
        name_a = tr.select_one("td.hauptlink a")
        if not name_a:
            continue
        # Positie staat in de geneste 'inline-table' (2e rij)
        inline_rows = tr.select("table.inline-table tr")
        position = inline_rows[1].get_text(strip=True) if len(inline_rows) > 1 else ""
        centered = [td.get_text(strip=True) for td in tr.select("td.zentriert")]
        value_td = tr.select_one("td.rechts.hauptlink")
        players.append({
            "name": name_a.get_text(strip=True),
            "profile_url": "https://www.transfermarkt.be" + name_a["href"],
            "position": position,
            "birth_and_age": next((c for c in centered if "(" in c), ""),
            "market_value": value_td.get_text(strip=True) if value_td else "",
        })
    return players


def main(url: str):
    # uc=True + CDP-mode is de stealth-combinatie uit de video
    with SB(uc=True, test=True, locale="nl", headed=True) as sb:
        html = fetch_html(sb, url)
    players = parse_squad(html)
    if not players:
        print("Geen spelers gevonden: selectors aanpassen aan de huidige HTML.")
        return
    with open("squad.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=players[0].keys())
        w.writeheader()
        w.writerows(players)
    print(f"{len(players)} spelers opgeslagen in squad.csv")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
