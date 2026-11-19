#!/usr/bin/env python3
"""
Patch voor transfermarkt-scraper v0.4.0

Repareert twee bekende fragiele plekken:
1. players.py - de strikte xpath + assert faalt wanneer Transfermarkt
   zijn HTML-structuur aanpast. We vervangen de parse() door een robuustere
   versie die alle /spieler/ links op de pagina vindt.
2. appearances.py - full_stats_href kan None zijn (bekende bug).

Wordt uitgevoerd door de workflow NA het clonen van de scraper.
"""
import os
import re
from pathlib import Path
import sys

SCRAPER_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SCRAPER_DIR', '/tmp/scraper'))

def patch_players():
    """Vervang de fragile parse() in players.py door een robuuste versie."""
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'players.py'
    if not fpath.exists():
        print(f"  players.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    # Zoek de originele parse() method en vervang hem
    new_parse = '''  def parse(self, response, parent):
      """Parse club's page to collect player URLs. Robuuste versie.
      Vindt alle unieke /spieler/<id>/ links op de pagina, ongeacht
      exacte tabel-structuur. Transfermarkt past HTML regelmatig aan,
      dus we zoeken breed en deduplicaten op player-ID.
      """
      import re as _re
      # Vind alle hrefs die naar /spieler/ wijzen (spelerprofiel)
      all_hrefs = response.xpath('//a/@href').getall()
      seen = set()
      player_hrefs = []
      for h in all_hrefs:
          if not h:
              continue
          # Match /<naam>/profil/spieler/<id>
          m = _re.search(r'(/[^/]+/profil/spieler/\\d+)', h)
          if m:
              canonical = m.group(1)
              if canonical not in seen:
                  seen.add(canonical)
                  player_hrefs.append(canonical)

      self.logger.info(
          "players.parse: %d unieke spelers gevonden op %s",
          len(player_hrefs), response.url
      )

      if not player_hrefs:
          self.logger.warning("GEEN spelers gevonden op %s", response.url)
          return

      for href in player_hrefs:
          cb_kwargs = {
              'base': {
                  'type': 'player',
                  'href': href,
                  'parent': parent
              }
          }
          yield response.follow(href, self.parse_details, cb_kwargs=cb_kwargs)

'''

    # Vervang van 'def parse(self, response, parent):' t/m de eerste 'def parse_details'
    pattern = re.compile(
        r'  def parse\(self, response, parent\):.*?(?=  def parse_details)',
        re.DOTALL
    )
    if not pattern.search(src):
        print("  players.py: kon originele parse() niet vinden - overslaan")
        return False

    new_src = pattern.sub(lambda m: new_parse, src, count=1)
    fpath.write_text(new_src, encoding='utf-8')
    print("  ✅ players.py: parse() vervangen door robuuste versie")
    return True


def patch_clubs():
    """Voegt club-naam extractie toe aan clubs.py.

    De originele parse() haalt alleen de href van elk team uit de
    competitie-tabel, nooit de naam zelf. Daardoor is 'name' in de
    workflow-merge altijd leeg. Fix: pak ook de anchor-tekst (of title-
    attribuut als fallback) uit dezelfde tabelcel en geef hem mee in
    cb_kwargs['base'], zodat hij in parse_details()'s {**base, **attributes}
    terechtkomt.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'clubs.py'
    if not fpath.exists():
        print(f"  clubs.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if 'extract_team_name' in src:
        print("  clubs.py: naam-extractie bestaat al - overslaan")
        return True

    old_extract = (
        "    def extract_team_href(row):\n"
        "        \"\"\"It extracts one team's href from a teams' table row\"\"\"\n"
        "        return row.css('td')[1].css('a::attr(href)').get()\n"
    )
    new_extract = (
        old_extract + "\n"
        "    def extract_team_name(row):\n"
        "        \"\"\"It extracts one team's display name from a teams' table row\"\"\"\n"
        "        name = row.css('td')[1].css('a::text').get()\n"
        "        if name:\n"
        "            return name.strip()\n"
        "        return row.css('td')[1].css('a::attr(title)').get()\n"
    )
    if old_extract not in src:
        print("  clubs.py: extract_team_href() niet gevonden - overslaan")
        return False
    src = src.replace(old_extract, new_extract, 1)

    old_cb = (
        "        cb_kwargs = {\n"
        "          'base' : {\n"
        "            'type': 'club',\n"
        "            'href': href_strip_season,\n"
        "            'parent': parent\n"
        "          }\n"
        "        }\n"
    )
    new_cb = (
        "        name = extract_team_name(row)\n"
        "\n"
        "        cb_kwargs = {\n"
        "          'base' : {\n"
        "            'type': 'club',\n"
        "            'href': href_strip_season,\n"
        "            'name': name,\n"
        "            'parent': parent\n"
        "          }\n"
        "        }\n"
    )
    if old_cb not in src:
        print("  clubs.py: cb_kwargs block niet gevonden - overslaan")
        return False
    src = src.replace(old_cb, new_cb, 1)

    fpath.write_text(src, encoding='utf-8')
    print("  ✅ clubs.py: club-naam extractie toegevoegd")
    return True


def patch_club_market_value():
    """Fix total_market_value in clubs.py: oude 'dataMarktwert'-div bestaat
    niet meer.

    Transfermarkt's club-pagina is herbouwd; de marktwaarde staat nu in
    <a class="data-header__market-value-wrapper">, met het bedrag en de
    munteenheid in aparte <span>'s rond de tekst zelf, bv.
      <a class="data-header__market-value-wrapper">
        <span class="waehrung">€</span>238.20<span class="waehrung">M</span>
        <p class="data-header__last-update">Total market value</p>
      </a>
    Alle tekstnodes die GEEN kind zijn van de 'Total market value'-<p>
    samenvoegen geeft "€238.20M". Bevestigd tegen de live Club Brugge-pagina.

    coach_name kon nergens meer op deze pagina teruggevonden worden (geen
    'Mitarbeiter'/coach-sectie meer aanwezig) - die blijft leeg, geen fix
    mogelijk zonder een andere databron.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'clubs.py'
    if not fpath.exists():
        print(f"  clubs.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    old_line = "    attributes['total_market_value'] = response.css('div.dataMarktwert a::text').get()"
    new_line = (
        "    market_value_parts = [\n"
        "      t.strip() for t in response.xpath(\n"
        "        \"//a[contains(@class,'data-header__market-value-wrapper')]\"\n"
        "        \"//text()[not(ancestor::p)]\"\n"
        "      ).getall() if t.strip()\n"
        "    ]\n"
        "    attributes['total_market_value'] = ''.join(market_value_parts) or None"
    )

    if new_line in src:
        print("  clubs.py: market-value-patch bestaat al - overslaan")
        return True
    if old_line not in src:
        print("  clubs.py: oude total_market_value-regel niet gevonden - overslaan")
        return False

    src = src.replace(old_line, new_line, 1)
    fpath.write_text(src, encoding='utf-8')
    print("  ✅ clubs.py: total_market_value-selector bijgewerkt")
    return True


def patch_club_images():
    """Voegt crest_url, competition_logo_url en country_flag_url toe aan clubs.py.

    Alle drie staan al op de clubpagina zelf (bevestigd live tegen Club
    Brugge): het clublogo in div.data-header__profile-container (vaste
    src, niet lazy-loaded), het competitielogo in de "League level"-link
    bovenaan (srcset met een 1x/2x variant - we nemen de hoogste
    resolutie), en de landvlag naast "League level:" (lazy-loaded, dus
    @data-src i.p.v. @src).
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'clubs.py'
    if not fpath.exists():
        print(f"  clubs.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if "attributes['crest_url']" in src:
        print("  clubs.py: logo/vlag-extractie bestaat al - overslaan")
        return True

    marker = "    attributes['total_market_value'] = ''.join(market_value_parts) or None\n"
    if marker not in src:
        print("  clubs.py: anker voor logo/vlag-extractie niet gevonden - overslaan")
        return False

    addition = (
        marker +
        "\n"
        "    attributes['crest_url'] = response.xpath(\n"
        "      \"//div[@class='data-header__profile-container']/img/@src\"\n"
        "    ).get()\n"
        "\n"
        "    competition_logo_srcset = response.xpath(\n"
        "      \"//a[contains(@class,'data-header__box__club-link')]/img/@srcset\"\n"
        "    ).get()\n"
        "    if competition_logo_srcset:\n"
        "      logo_candidates = [\n"
        "        c.strip().rsplit(' ', 1)[0] for c in competition_logo_srcset.split(',') if c.strip()\n"
        "      ]\n"
        "      attributes['competition_logo_url'] = logo_candidates[-1] if logo_candidates else None\n"
        "    else:\n"
        "      attributes['competition_logo_url'] = None\n"
        "\n"
        "    attributes['country_flag_url'] = response.xpath(\n"
        "      \"//strong[contains(text(),'League level')]/following-sibling::span[1]/a/img/@data-src\"\n"
        "    ).get()\n"
    )
    src = src.replace(marker, addition, 1)
    fpath.write_text(src, encoding='utf-8')
    print("  ✅ clubs.py: crest_url, competition_logo_url en country_flag_url toegevoegd")
    return True


def patch_player_names():
    """Voegt voornaam/achternaam extractie toe aan players.py.

    parse_details() haalt tientallen velden uit de profielpagina, maar
    nooit de naam zelf - 'name'/'last_name' bestaan niet in de originele
    scraper. De workflow-merge verwacht wel degelijk dat 'name' (voornaam)
    en 'last_name' (achternaam) bestaan (zie monthly_update.yml, waar ze
    worden samengevoegd tot de volledige naam).

    Bron: de headline op de profielpagina, bv.
      <h1 class="data-header__headline-wrapper">
        <span class="data-header__shirt-number">#11</span>
        Kevin <strong>De Bruyne</strong>
      </h1>
    De voornaam is directe tekst van de h1 (shirtnummer-span en <strong>
    tellen niet mee); de achternaam staat in <strong>.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'players.py'
    if not fpath.exists():
        print(f"  players.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if "attributes['last_name']" in src:
        print("  players.py: naam-extractie bestaat al - overslaan")
        return True

    marker = "    attributes = {}\n\n    attributes['name_in_home_country']"
    if marker not in src:
        print("  players.py: anker voor naam-extractie niet gevonden - overslaan")
        return False

    name_block = (
        "    attributes = {}\n"
        "\n"
        "    # PATCH: voornaam/achternaam uit de headline halen (nooit in de originele scraper)\n"
        "    first_name_parts = [\n"
        "      t.strip() for t in response.xpath(\n"
        "        \"//h1[contains(@class,'data-header__headline-wrapper')]/text()\"\n"
        "      ).getall() if t.strip()\n"
        "    ]\n"
        "    attributes['name'] = ' '.join(first_name_parts)\n"
        "    attributes['last_name'] = self.safe_strip(\n"
        "      response.xpath(\n"
        "        \"//h1[contains(@class,'data-header__headline-wrapper')]/strong/text()\"\n"
        "      ).get()\n"
        "    ) or ''\n"
        "\n"
        "    attributes['name_in_home_country']"
    )
    src = src.replace(marker, name_block, 1)
    fpath.write_text(src, encoding='utf-8')
    print("  ✅ players.py: voornaam/achternaam extractie toegevoegd")
    return True


def patch_current_club_name():
    """Haalt ook de NAAM van de huidige club op, niet enkel de href.

    Gevonden tijdens een datacontrole: de merge gebruikte voorheen de club
    waar een speler toevallig onder gevonden werd (via de squad-lijst) i.p.v.
    zijn eigen 'Current club'-veld op zijn profielpagina. Een speler die naar
    een niet-gescrapede competitie vertrok (bv. naar de Bundesliga terwijl
    enkel 'core' draait) bleef daardoor voor altijd bij zijn oude club/
    competitie "vastgevroren" staan in players.csv (zie Antonio Nusa:
    transfers/marktwaarde/optredens klopten, current_club niet).

    De href zat er al, maar de bijhorende naam niet: het "Current club:"-
    blok bevat TWEE <a>-tags (eerste wrapt enkel het clublogo, geen tekst;
    tweede heeft de clubnaam als tekst) - alle tekstnodes ophalen en de
    eerste niet-lege nemen geeft betrouwbaar de naam.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'players.py'
    if not fpath.exists():
        print(f"  players.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    old_block = (
        "    attributes['current_club'] = {\n"
        "      'href': response.xpath(\"//span[contains(text(),'Current club:')]/following::span[1]/a/@href\").get()\n"
        "    }\n"
    )
    new_block = (
        "    current_club_texts = response.xpath(\n"
        "      \"//span[contains(text(),'Current club:')]/following::span[1]/a/text()\"\n"
        "    ).getall()\n"
        "    current_club_name = next((t.strip() for t in current_club_texts if t.strip()), None)\n"
        "    attributes['current_club'] = {\n"
        "      'href': response.xpath(\"//span[contains(text(),'Current club:')]/following::span[1]/a/@href\").get(),\n"
        "      'name': current_club_name,\n"
        "    }\n"
    )

    if "'name': current_club_name" in src:
        print("  players.py: current_club naam-extractie bestaat al - overslaan")
        return True
    if old_block not in src:
        print("  players.py: current_club-blok niet gevonden - overslaan")
        return False

    src = src.replace(old_block, new_block, 1)
    fpath.write_text(src, encoding='utf-8')
    print("  ✅ players.py: current_club bevat nu ook de naam")
    return True


def patch_player_flags():
    """Voegt vlag-URL's toe aan players.py: citizenship_flag_url en
    place_of_birth.flag_url.

    Beide vlag-afbeeldingen stonden al op de pagina (enkel @title - de
    landnaam - werd ooit uitgelezen). Citizenship's vlag is niet lazy-
    loaded (@src rechtstreeks bruikbaar); place_of_birth's vlag zit in een
    lazy-loaded element (@src is een base64-placeholder, de echte url
    staat in @data-src). Bevestigd live tegen Kevin De Bruyne's profiel.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'players.py'
    if not fpath.exists():
        print(f"  players.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if "citizenship_flag_url" in src:
        print("  players.py: vlag-URL extractie bestaat al - overslaan")
        return True

    old_place = (
        "    attributes['place_of_birth'] = {\n"
        "      'country': response.xpath(\"//span[text()='Place of birth:']/following::span[1]/span/img/@title\").get(),\n"
        "      'city': response.xpath(\"//span[text()='Place of birth:']/following::span[1]/span/text()\").get()\n"
        "    }\n"
    )
    new_place = (
        "    attributes['place_of_birth'] = {\n"
        "      'country': response.xpath(\"//span[text()='Place of birth:']/following::span[1]/span/img/@title\").get(),\n"
        "      'city': response.xpath(\"//span[text()='Place of birth:']/following::span[1]/span/text()\").get(),\n"
        "      'flag_url': response.xpath(\"//span[text()='Place of birth:']/following::span[1]/span/img/@data-src\").get()\n"
        "    }\n"
    )
    if old_place not in src:
        print("  players.py: place_of_birth-blok niet gevonden - overslaan")
        return False
    src = src.replace(old_place, new_place, 1)

    old_citizenship = "    attributes['citizenship'] = response.xpath(\"//span[text()='Citizenship:']/following::span[1]/img/@title\").get()\n"
    new_citizenship = (
        old_citizenship +
        "    attributes['citizenship_flag_url'] = response.xpath(\"//span[text()='Citizenship:']/following::span[1]/img/@src\").get()\n"
    )
    if old_citizenship not in src:
        print("  players.py: citizenship-regel niet gevonden - overslaan")
        return False
    src = src.replace(old_citizenship, new_citizenship, 1)

    fpath.write_text(src, encoding='utf-8')
    print("  ✅ players.py: citizenship_flag_url en place_of_birth.flag_url toegevoegd")
    return True


def patch_player_birthdate_age():
    """Fix date_of_birth/age in players.py: Transfermarkt heeft de losse
    'Date of birth:' en 'Age:' labels samengevoegd tot één label
    'Date of birth/Age:' (bv. "28/06/1991 (35)"). De oude exacte-tekst
    xpaths ("//span[text()='Date of birth:']" / "//span[text()='Age:']")
    matchen daardoor nergens meer op de pagina en geven altijd None - elke
    speler die herscraped wordt verliest zo zijn geboortedatum EN leeftijd
    (bevestigd live: Erling Haaland, Anton Stach, ... stonden na de laatste
    big5-run allebei leeg).

    Fix: de waarde staat intact in een stabiel microdata-attribuut,
    <span itemprop="birthDate">28/06/1991 (35)</span> - datum en leeftijd
    daar met een regex uit halen i.p.v. op het (nu dubbelzinnige) label te
    zoeken.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'players.py'
    if not fpath.exists():
        print(f"  players.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if "itemprop='birthDate'" in src:
        print("  players.py: geboortedatum/leeftijd-fix bestaat al - overslaan")
        return True

    old_block = (
        "    attributes['name_in_home_country'] = response.xpath(\"//span[text()='Name in home country:']/following::span[1]/text()\").get()\n"
        "    attributes['date_of_birth'] = response.xpath(\"//span[text()='Date of birth:']/following::span[1]//text()\").get()\n"
    )
    new_block = (
        "    attributes['name_in_home_country'] = response.xpath(\"//span[text()='Name in home country:']/following::span[1]/text()\").get()\n"
        "\n"
        "    # PATCH: 'Date of birth:' en 'Age:' zijn samengevoegd tot één label op\n"
        "    # TM - de waarde zelf staat nog intact in dit microdata-attribuut.\n"
        "    birth_date_age_text = self.safe_strip(\n"
        "      response.xpath(\"//span[@itemprop='birthDate']/text()\").get()\n"
        "    ) or ''\n"
        "    dob_match = re.search(r'(\\d{1,2}/\\d{1,2}/\\d{4})', birth_date_age_text)\n"
        "    age_match = re.search(r'\\((\\d+)\\)', birth_date_age_text)\n"
        "    attributes['date_of_birth'] = dob_match.group(1) if dob_match else None\n"
        "    attributes['age'] = age_match.group(1) if age_match else None\n"
    )

    if old_block not in src:
        print("  players.py: anker voor geboortedatum-fix niet gevonden - overslaan")
        return False
    src = src.replace(old_block, new_block, 1)

    old_age_line = "    attributes['age'] = response.xpath(\"//span[text()='Age:']/following::span[1]/text()\").get()\n"
    if old_age_line in src:
        src = src.replace(old_age_line, "", 1)
    elif "attributes['age'] = age_match" not in src:
        print("  players.py: oude age-regel niet gevonden (versie-mismatch?) - overslaan")
        return False

    fpath.write_text(src, encoding='utf-8')
    print("  ✅ players.py: date_of_birth/age-extractie hersteld (itemprop='birthDate')")
    return True


def patch_appearances():
    """Fix appearances.py waar full_stats_href None kan zijn.

    De originele parse() methode gebruikt een xpath om de 'full stats' link
    te vinden op de speler-profielpagina. In 2025 is die xpath niet meer
    betrouwbaar - hij matcht soms niets, waarna de spider crasht met:
        TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'

    Fix: als full_stats_href None is, probeer een fallback op basis van de
    speler-URL (die heeft een deterministische relatie met de stats-URL).
    Als dat ook niet lukt: skip deze speler netjes.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'appearances.py'
    if not fpath.exists():
        print("  appearances.py niet gevonden - overslaan")
        return False

    src = fpath.read_text(encoding='utf-8')

    # Vind de crashende regel en behoud de bestaande indentatie
    # Regex: optionele whitespace + "seasoned_full_stats_href = full_stats_href..."
    pattern = re.compile(
        r'^([ \t]*)seasoned_full_stats_href = full_stats_href \+ f"/plus/0\?saison=\{season\}"',
        re.MULTILINE
    )
    m = pattern.search(src)
    if not m:
        print("  appearances.py: crashende regel niet gevonden (versie mismatch?) - overslaan")
        return False

    indent = m.group(1)  # behoud exacte indentatie (spaties of tabs)

    # Bouw vervangende block met dezelfde indentatie
    new_block = (
        f'{indent}# PATCH: fallback als full_stats_href None is (TM HTML aanpassing)\n'
        f'{indent}if full_stats_href is None:\n'
        f'{indent}    profile_path = response.url.split("transfermarkt.co.uk")[-1].split("transfermarkt.com")[-1]\n'
        f'{indent}    if "/profil/spieler/" in profile_path:\n'
        f'{indent}        full_stats_href = profile_path.replace("/profil/spieler/", "/leistungsdatendetails/spieler/")\n'
        f'{indent}        self.logger.info("appearances: fallback URL gebruikt voor %s", response.url)\n'
        f'{indent}    else:\n'
        f'{indent}        self.logger.warning("appearances: geen full_stats_href en geen fallback voor %s - overslaan", response.url)\n'
        f'{indent}        return\n'
        f'{indent}seasoned_full_stats_href = full_stats_href + f"/plus/0?saison={{season}}"'
    )

    new_src = pattern.sub(lambda _m: new_block, src, count=1)
    if new_src == src:
        print("  appearances.py: vervanging mislukt - overslaan")
        return False

    # Extra fix uit dcaribou main-branch: TM heeft 'div.table-header' vervangen
    # door 'div.content-box-headline' voor de competitie-namen bij stats-tabellen.
    # Issue #34 in dcaribou/transfermarkt-scraper.
    old_css = "response.css(\n        'div.table-header > a::attr(name)'\n    ).getall()"
    new_css = "response.css('div.content-box-headline > a::attr(name)').getall()"
    if old_css in new_src:
        new_src = new_src.replace(old_css, new_css)
        print("  ✅ appearances.py: CSS-selector bijgewerkt (table-header -> content-box-headline)")
    else:
        # Probeer een minder specifieke match (een-regelige variant)
        alt_old = "response.css('div.table-header > a::attr(name)').getall()"
        if alt_old in new_src:
            new_src = new_src.replace(alt_old, new_css)
            print("  ✅ appearances.py: CSS-selector bijgewerkt (table-header -> content-box-headline)")
        else:
            print("  ⚠ appearances.py: oude CSS-selector niet gevonden (al bijgewerkt?)")

    fpath.write_text(new_src, encoding='utf-8')
    print(f"  ✅ appearances.py: None-guard + fallback toegevoegd (indent={len(indent)} chars)")
    return True


def patch_common():
    """Koppel de oude start_requests() override aan Scrapy's nieuwere async
    start() entrypoint. Recente Scrapy-versies (2.13+) roepen start() aan
    i.p.v. start_requests() rechtstreeks te gebruiken; zonder deze brug valt
    Scrapy terug op self.start_urls (die BaseSpider nooit definieert), met
    een AttributeError tot gevolg.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'common.py'
    if not fpath.exists():
        print(f"  common.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if 'async def start(self)' in src:
        print("  common.py: start() bridge bestaat al - overslaan")
        return True

    marker = '  def start_requests(self):'
    if marker not in src:
        print("  common.py: start_requests() niet gevonden - overslaan")
        return False

    bridge = (
        '  async def start(self):\n'
        '    for request in self.start_requests():\n'
        '      yield request\n\n'
    )
    new_src = src.replace(marker, bridge + marker, 1)
    fpath.write_text(new_src, encoding='utf-8')
    print("  ✅ common.py: start() bridge naar start_requests() toegevoegd")
    return True


def patch_club_tiers():
    """Laat de clubs-spider ook second_tier t/m fifth_tier competities verwerken.

    start_requests() in common.py slaat van oudsher alles behalve
    'first_tier' over voor de clubs-spider. Daardoor worden clubs/spelers
    van lagere klasses (BE2, PO2, TR2, A2, C2, NL2, GRS2, GB3/GB4/CNAT,
    L3, E3G1/E3G2, IT3A-C, FR3, NTD, ...) nooit ververst - enkel
    wedstrijden (games-spider), want die heeft deze beperking niet.
    Playoff-competities blijven overgeslagen: die pagina's hebben geen
    spelerslijst-tabel, dus clubs.py's assert(len(with_teams_info) == 1)
    zou daar toch altijd falen.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'common.py'
    if not fpath.exists():
        print(f"  common.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    old_check = "if self.name == 'clubs' and item['competition_type'] != 'first_tier':"
    new_check = (
        "if self.name == 'clubs' and item['competition_type'] not in "
        "('first_tier', 'second_tier', 'third_tier', 'fourth_tier', 'fifth_tier'):"
    )

    if new_check in src:
        print("  common.py: second_tier-patch bestaat al - overslaan")
        return True

    if old_check not in src:
        print("  common.py: first_tier-check niet gevonden - overslaan")
        return False

    new_src = src.replace(old_check, new_check, 1)
    fpath.write_text(new_src, encoding='utf-8')
    print("  ✅ common.py: clubs-spider verwerkt nu ook second_tier t/m fifth_tier competities")
    return True


def patch_games_fallback():
    """Fallback voor games.py wanneer de competitiepagina geen footer-links
    meer heeft.

    UEFA Champions/Europa/Conference League en de landenploegen-toernooien
    (WK, EK, Nations League, Copa América, Afrika Cup) hebben een volledig
    JS-rendered landingspagina (0 <table> elementen, geen footer-links) -
    parse() vindt daardoor nooit de 'All fixtures & results'-link en
    retourneert stil niets.

    De eigenlijke wedstrijdenlijst-pagina ('gesamtspielplan') bestaat wel
    nog als klassieke server-rendered pagina, op een voorspelbare URL:
    <slug>/gesamtspielplan/pokalwettbewerb/<CODE>/saison_id/<season>
    (bevestigd door de embedded JSON op de CL/UCOL/FIWC/EURO/COPA/AFCN
    landingspagina's zelf op te vragen). Als de footer-link niet gevonden
    wordt, bouwen we die URL rechtstreeks op als fallback.
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'games.py'
    if not fpath.exists():
        print(f"  games.py niet gevonden op {fpath}")
        return False

    src = fpath.read_text(encoding='utf-8')

    if 'gesamtspielplan/pokalwettbewerb' in src:
        print("  games.py: fallback bestaat al - overslaan")
        return True

    old_block = (
        "        return response.follow(next_url, self.extract_game_urls, cb_kwargs=cb_kwargs)\n"
    )
    new_block = (
        "        return response.follow(next_url, self.extract_game_urls, cb_kwargs=cb_kwargs)\n"
        "\n"
        "    # PATCH: nieuwere, volledig JS-rendered competitiepagina's (CL/EL/UCOL,\n"
        "    # landenploegen-toernooien) hebben geen footer-links meer. De\n"
        "    # wedstrijdenlijst zelf is nog wel server-rendered - rechtstreeks\n"
        "    # opbouwen als fallback.\n"
        "    if 'startseite/wettbewerb' in parent['href']:\n"
        "      fallback_path = parent['href'].replace(\n"
        "        'startseite/wettbewerb', 'gesamtspielplan/pokalwettbewerb'\n"
        "      ) + f'/saison_id/{self.season}'\n"
        "      return response.follow(fallback_path, self.extract_game_urls, cb_kwargs=cb_kwargs)\n"
    )
    if old_block not in src:
        print("  games.py: anker voor fallback niet gevonden - overslaan")
        return False

    new_src = src.replace(old_block, new_block, 1)
    fpath.write_text(new_src, encoding='utf-8')
    print("  ✅ games.py: fallback voor JS-rendered competitiepagina's toegevoegd")
    return True


def add_injuries_spider():
    """Voegt een nieuwe 'injuries'-spider toe aan de gecloonde scraper.

    Bestaat niet upstream - transfermarkt-scraper haalt enkel bio/
    appearances/games/competities op, nooit blessurehistoriek. De
    blessurepagina (<speler-href>/verletzungen/spieler/<id>, met
    '/profil/spieler/' vervangen door '/verletzungen/spieler/') heeft
    dezelfde 'table.items'-opbouw als de rest van Transfermarkt:
    Season | Injury | from | until | Days | Games missed. De laatste
    kolom bevat een club/land-wapen plus een <span> met het aantal
    gemiste wedstrijden, of een kale "-" als er geen wedstrijden gemist
    zijn (bv. een blessure die net na het seizoen begon).

    Draait tegen data/raw/players.json als parents (één keer, niet per
    seizoen - de pagina toont sowieso de volledige carrière-historiek).
    """
    fpath = SCRAPER_DIR / 'tfmkt' / 'spiders' / 'injuries.py'
    fpath.write_text(
        "from tfmkt.spiders.common import BaseSpider\n"
        "\n"
        "class InjuriesSpider(BaseSpider):\n"
        "  name = 'injuries'\n"
        "\n"
        "  def parse(self, response, parent):\n"
        "    \"\"\"Van de spelerspagina door naar de blessurehistoriek-pagina.\n"
        "\n"
        "    @url https://www.transfermarkt.co.uk/erling-haaland/profil/spieler/418560\n"
        "    @returns requests 1 1\n"
        "    @cb_kwargs {\"parent\": \"dummy\"}\n"
        "    \"\"\"\n"
        "    injury_href = parent['href'].replace('/profil/spieler/', '/verletzungen/spieler/')\n"
        "    yield response.follow(injury_href, self.parse_injuries, cb_kwargs={'parent': parent})\n"
        "\n"
        "  def parse_injuries(self, response, parent):\n"
        "    \"\"\"Parse de blessuretabel.\n"
        "\n"
        "    @url https://www.transfermarkt.co.uk/erling-haaland/verletzungen/spieler/418560\n"
        "    @returns items 0 50\n"
        "    @cb_kwargs {\"parent\": {\"href\": \"some_href\", \"type\": \"player\", \"parent\": {}}}\n"
        "    @scrapes type parent season injury from_date until_date days games_missed\n"
        "    \"\"\"\n"
        "    tables = response.css('table.items')\n"
        "    if not tables:\n"
        "      self.logger.info('injuries: geen blessuretabel op %s (speler nooit geblesseerd of pagina leeg)', response.url)\n"
        "      return\n"
        "\n"
        "    for row in tables[0].css('tr'):\n"
        "      cells = row.css('td')\n"
        "      if len(cells) < 6:\n"
        "        continue  # header-rij of onverwachte structuur\n"
        "\n"
        "      games_missed = self.safe_strip(cells[5].css('span::text').get())\n"
        "\n"
        "      yield {\n"
        "        'type': 'injury',\n"
        "        'parent': parent,\n"
        "        'season': self.safe_strip(cells[0].css('::text').get()),\n"
        "        'injury': self.safe_strip(cells[1].css('::text').get()),\n"
        "        'from_date': self.safe_strip(cells[2].css('::text').get()),\n"
        "        'until_date': self.safe_strip(cells[3].css('::text').get()),\n"
        "        'days': self.safe_strip(cells[4].css('::text').get()),\n"
        "        'games_missed': games_missed if games_missed else '0',\n"
        "      }\n",
        encoding='utf-8',
    )
    print("  ✅ injuries.py: nieuwe spider aangemaakt")
    return True


def main():
    print("=== Scraper patch script ===")
    print(f"Scraper directory: {SCRAPER_DIR}")
    if not SCRAPER_DIR.exists():
        print("FOUT: scraper directory bestaat niet!")
        sys.exit(1)

    patch_players()
    patch_clubs()
    patch_club_market_value()
    patch_club_images()
    patch_player_names()
    patch_current_club_name()
    patch_player_flags()
    patch_player_birthdate_age()
    patch_appearances()
    patch_common()
    patch_club_tiers()
    patch_games_fallback()
    add_injuries_spider()
    print("=== Patches klaar ===")


if __name__ == '__main__':
    main()
