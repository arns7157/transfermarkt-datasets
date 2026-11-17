#!/usr/bin/env python3
"""
Herbruikbare CSV-decompressie/merge-logica voor monthly_update.yml.

Losgetrokken uit de workflow zelf (was voorheen twee losse inline
python-heredocs, "Stap 0" en "Stap 5") zodat de retry-lus in de
"Commit en push CSVs"-stap dit opnieuw kan uitvoeren tegen de nieuwste
data/csv/-stand als een andere run intussen al gepusht heeft.

Waarom dit nodig is: elke run herschrijft alle CSV's volledig, dus elke
data-commit raakt letterlijk elk .csv.gz-bestand. Git kan twee binaire
bestanden nooit automatisch samenvoegen (git rebase/merge op deze
bestanden loopt dan ook gegarandeerd vast, niet toevallig soms). De
enige correcte fix bij een botsing is: de eigen commit weggooien,
data/csv/ resetten naar de nieuwste gepushte stand, en dit script
opnieuw laten draaien tegen die verse basis - de reeds opgehaalde ruwe
JSON in data/raw/ (nooit in git, dus overleeft een "git reset --hard"
probleem) wordt dan correct samengevoegd met wat de andere run intussen
toevoegde, via de bestaande upsert-per-id logica hieronder.

Subcommands:
  decompress  - pakt data/csv/*.csv.gz uit naar platte .csv (voorheen "Stap 0")
  merge       - leest data/raw/*.json + de platte .csv's en schrijft de
                samengevoegde CSV's terug (voorheen "Stap 5")
"""
import gzip, shutil
from pathlib import Path
import json, csv, re
import sys


def decompress():
    CSV = Path('data/csv')
    for gz_file in sorted(CSV.glob('*.csv.gz')):
        stem = gz_file.stem
        out_name = 'appearances_existing.csv' if stem == 'appearances.csv' else stem
        out_path = CSV / out_name
        print(f"Decomprimeer {gz_file.name} -> {out_name} ({gz_file.stat().st_size // 1024} KB)")
        with gzip.open(gz_file, 'rb') as f_in:
            with open(out_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)


def merge():
    RAW = Path('data/raw')
    OUT = Path('data/csv')
    OUT.mkdir(exist_ok=True)
    def load_jsonl(path):
        items = []
        if not path.exists(): return items
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try: items.append(json.loads(line))
                    except: pass
        return items
    def load_csv_existing(path):
        rows = []
        if not path.exists(): return rows
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows
    def extract_id(href):
        if not href: return ''
        parts = href.rstrip('/').split('/')
        if 'wettbewerb' in parts: return parts[parts.index('wettbewerb') + 1]
        if 'verein' in parts: return parts[parts.index('verein') + 1]
        if 'spieler' in parts: return parts[parts.index('spieler') + 1]
        if 'spielbericht' in parts: return parts[parts.index('spielbericht') + 1]
        return parts[-1]
    def parse_market_value(mv_str):
        if not mv_str: return ''
        s = str(mv_str).strip()
        # Al een getal?
        try:
            v = int(float(s))
            if v > 0: return v
        except: pass
        # Verwijder valutasymbolen
        s = s.replace('€','').replace('£','').replace('$','').strip()
        s_low = s.lower()
        try:
            if 'mio' in s_low or s_low.endswith('m') or ' m' in s_low:
                s2 = s_low.replace('mio.','').replace('mio','').replace(' m','').replace('m','').replace(',','.').strip()
                return int(float(s2) * 1_000_000)
            if 'th.' in s_low or s_low.endswith('k') or ' k' in s_low or 'tsd' in s_low:
                s2 = s_low.replace('th.','').replace('tsd.','').replace('tsd','').replace(' k','').replace('k','').replace(',','.').strip()
                return int(float(s2) * 1_000)
            s2 = s.replace(',','.').strip()
            return int(float(s2))
        except: return ''
    # Laad marktwaarden
    mv_lookup = {}
    mv_file = RAW / 'market_values.json'
    if mv_file.exists():
        with open(mv_file, encoding='utf-8') as f:
            mv_raw = json.load(f)
            for pid, mv in mv_raw.items():
                mv_lookup[str(pid)] = parse_market_value(mv)
        print(f"Marktwaarden geladen: {len(mv_lookup)}")
    # PATCH: hoogste marktwaarde berekenen uit de volledige historische
    # reeks i.p.v. ze te lezen uit een losse HTML-div op de spelerspagina -
    # dat hele marktwaarde-widget is intussen een JS-component geworden
    # (tm-market-value-development-graph-integrated), dus de oude div
    # bestaat niet meer en highest_market_value_in_eur stond daardoor
    # altijd leeg. We kennen elke historische waarde toch al (zowel wat
    # al in player_valuations.csv stond als wat deze run net opgehaald
    # is via de marktwaarde-API) - het hoogste punt daarvan IS per
    # definitie de hoogste marktwaarde ooit.
    mv_highest_lookup = {}
    def _bump_highest(pid, val):
        if not pid or val in ('', None):
            return
        try:
            val = int(val)
        except (TypeError, ValueError):
            return
        if val > mv_highest_lookup.get(pid, 0):
            mv_highest_lookup[pid] = val
    for r in load_csv_existing(OUT / 'player_valuations.csv'):
        _bump_highest(str(r.get('player_id', '')), r.get('market_value_in_eur'))
    for v in load_jsonl(RAW / 'valuations.json'):
        pid = str(v.get('player_id', ''))
        vmv_raw = v.get('market_value_in_eur', '') or v.get('market_value', '') or v.get('mw', '')
        _bump_highest(pid, parse_market_value(str(vmv_raw)) if vmv_raw else '')
    print(f"Hoogste marktwaarde gekend voor {len(mv_highest_lookup)} spelers")
    # ── CLUBS ──
    clubs = load_jsonl(RAW / 'clubs.json')
    club_lookup = {}
    new_club_rows = []
    for c in clubs:
        comp_href = c.get('parent', {}).get('href', '')
        comp_id = extract_id(comp_href)
        club_id = c.get('id') or extract_id(c.get('href', ''))
        club_lookup[c.get('href', '')] = {'club_id': club_id, 'name': c.get('name', ''), 'competition_id': comp_id}
        new_club_rows.append({
            'club_id': club_id, 'name': c.get('name', ''),
            'domestic_competition_id': comp_id,
            'squad_size': c.get('squad_size', ''),
            'average_age': c.get('average_age', ''),
            'total_market_value': c.get('total_market_value', ''),
            'coach_name': c.get('coach_name', ''),
            'stadium_name': c.get('stadium_name', ''),
            'stadium_seats': c.get('stadium_seats', ''),
            'foreigners_number': c.get('foreigners_number', ''),
            'foreigners_percentage': c.get('foreigners_percentage', ''),
            'national_team_players': c.get('national_team_players', ''),
            'net_transfer_record': c.get('net_transfer_record', ''),
            'crest_url': c.get('crest_url', ''),
            'competition_logo_url': c.get('competition_logo_url', ''),
            'country_flag_url': c.get('country_flag_url', ''),
            'url': f"https://www.transfermarkt.co.uk{c.get('href', '')}",
        })
    existing_clubs = load_csv_existing(OUT / 'clubs.csv')
    club_id_map = {r['club_id']: r for r in existing_clubs if r.get('club_id')}
    for r in new_club_rows:
        cid = str(r.get('club_id', ''))
        if cid:
            old_row = club_id_map.get(cid)
            if old_row and not r.get('name') and old_row.get('name'):
                r['name'] = old_row['name']
            # Bewaar velden die deze run niet kon ophalen (bv. club niet in
            # deze batch, of selector miste iets) i.p.v. ze leeg te maken
            if old_row:
                for keep_col in [
                    'coach_name', 'stadium_name', 'stadium_seats',
                    'foreigners_number', 'foreigners_percentage',
                    'national_team_players', 'net_transfer_record',
                    'crest_url', 'competition_logo_url', 'country_flag_url',
                ]:
                    if not r.get(keep_col) and old_row.get(keep_col):
                        r[keep_col] = old_row[keep_col]
            club_id_map[cid] = r
    merged_clubs = list(club_id_map.values())
    if merged_clubs:
        club_cols = [
            'club_id', 'name', 'domestic_competition_id', 'squad_size',
            'average_age', 'total_market_value', 'coach_name',
            'stadium_name', 'stadium_seats', 'foreigners_number',
            'foreigners_percentage', 'national_team_players',
            'net_transfer_record', 'crest_url', 'competition_logo_url',
            'country_flag_url', 'url',
        ]
        with open(OUT / 'clubs.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=club_cols, extrasaction='ignore')
            w.writeheader()
            for row in merged_clubs:
                w.writerow({k: row.get(k, '') for k in club_cols})
        print(f'clubs.csv: {len(merged_clubs)} rijen (was {len(existing_clubs)}, +{len(merged_clubs)-len(existing_clubs)} nieuw)')
    # ── SPELERS ──
    debut_cols = [
        'hoogste_divisie_debut_date', 'hoogste_divisie_debut_club',
        'tweede_niveau_debut_date', 'tweede_niveau_debut_club',
        'debut_highest_division_date', 'debut_highest_division_club', 'debut_highest_division_competition',
        'debut_second_tier_date', 'debut_second_tier_club', 'debut_second_tier_competition',
    ]
    extra_player_cols = [
        'current_club_crest_url', 'current_club_competition_logo_url',
        'current_club_country_flag_url', 'name_in_home_country',
        'place_of_birth_city', 'country_of_birth_flag_url',
        'country_of_citizenship_flag_url', 'player_agent_name',
        'player_agent_href', 'joined', 'day_of_last_contract_extension',
        'outfitter', 'social_media',
    ]
    players = load_jsonl(RAW / 'players.json')
    new_player_rows = []
    for p in players:
        # PATCH: gebruik de EIGEN 'current_club' van de speler (van zijn
        # profielpagina) i.p.v. 'parent' (de club waar we hem toevallig
        # onder gevonden hebben via de squad-lijst). Een speler die naar
        # een niet-gescrapede competitie is vertrokken bleef anders voor
        # altijd bij zijn oude club/competitie "vastgevroren" staan.
        # club_id_map (hierboven opgebouwd, bevat zowel oude als nieuw
        # gescrapede clubs) geeft de beste kans op een juiste naam en
        # competitie_id, ook als die club deze run niet zelf gescraped is.
        own_current_club = p.get('current_club') or {}
        club_href = own_current_club.get('href', '') or p.get('parent', {}).get('href', '')
        current_club_id = extract_id(club_href)
        club_record = club_id_map.get(str(current_club_id), {}) if current_club_id else {}
        club_info = {
            'club_id': current_club_id,
            'name': club_record.get('name', '') or own_current_club.get('name', ''),
            'competition_id': club_record.get('domestic_competition_id', ''),
            'crest_url': club_record.get('crest_url', ''),
            'competition_logo_url': club_record.get('competition_logo_url', ''),
            'country_flag_url': club_record.get('country_flag_url', ''),
        }
        player_id = p.get('id') or extract_id(p.get('href', ''))
        height_raw = p.get('height', '') or ''
        # PATCH: transfermarkt.co.uk toont lengte nu soms als "5 ft 11 in"
        # i.p.v. het oude metrische "1,85m" - probeer dat formaat eerst.
        ft_in_match = re.match(r'\s*(\d+)\s*ft\s*(\d+)\s*in', height_raw)
        if ft_in_match:
            feet, inches = int(ft_in_match.group(1)), int(ft_in_match.group(2))
            height_cm = round(feet * 30.48 + inches * 2.54)
        else:
            try: height_cm = int(float(height_raw.replace('m','').replace(',','.').strip()) * 100)
            except: height_cm = ''
        pos = p.get('position', '') or ''
        pos_map = {
            'goalkeeper': 'Goalkeeper',
            'centre-back': 'Defender', 'left-back': 'Defender', 'right-back': 'Defender', 'defender': 'Defender',
            'attacking midfield': 'Midfield', 'midfielder': 'Midfield', 'midfield': 'Midfield',
            'centre-forward': 'Attack', 'left winger': 'Attack', 'right winger': 'Attack', 'forward': 'Attack', 'attack': 'Attack'
        }
        position = next((v for k, v in pos_map.items() if k in pos.lower()), 'Midfield')
        mv = mv_lookup.get(str(player_id), '')
        if not mv:
            mv_raw = p.get('current_market_value') or p.get('market_value') or ''
            if mv_raw:
                mv = parse_market_value(str(mv_raw))
        _bump_highest(str(player_id), mv)
        mv_high = mv_highest_lookup.get(str(player_id), '')
        if not mv_high:
            mv_high_raw = p.get('highest_market_value') or ''
            mv_high = parse_market_value(str(mv_high_raw)) if mv_high_raw else ''
        first_name = p.get('name', '') or ''
        last_name = p.get('last_name', '') or ''
        full_name = f"{first_name} {last_name}".strip() or first_name
        new_player_rows.append({
            'player_id': player_id, 'name': full_name,
            'first_name': first_name, 'last_name': last_name,
            'date_of_birth': p.get('date_of_birth', ''), 'age': p.get('age', ''),
            'country_of_citizenship': p.get('citizenship', ''),
            'country_of_birth': (p.get('place_of_birth') or {}).get('country', ''),
            'position': position, 'sub_position': pos,
            'foot': p.get('foot', ''), 'height_in_cm': height_cm,
            'market_value_in_eur': mv, 'highest_market_value_in_eur': mv_high,
            'contract_expiration_date': p.get('contract_expires', ''),
            'current_club_id': club_info.get('club_id', ''),
            'current_club_name': club_info.get('name', ''),
            'current_club_domestic_competition_id': club_info.get('competition_id', ''),
            'current_club_crest_url': club_info.get('crest_url', ''),
            'current_club_competition_logo_url': club_info.get('competition_logo_url', ''),
            'current_club_country_flag_url': club_info.get('country_flag_url', ''),
            'image_url': p.get('image_url', ''),
            'name_in_home_country': p.get('name_in_home_country', ''),
            'place_of_birth_city': (p.get('place_of_birth') or {}).get('city', ''),
            'country_of_birth_flag_url': (p.get('place_of_birth') or {}).get('flag_url', ''),
            'country_of_citizenship_flag_url': p.get('citizenship_flag_url', ''),
            'player_agent_name': (p.get('player_agent') or {}).get('name', ''),
            'player_agent_href': (p.get('player_agent') or {}).get('href', ''),
            'joined': p.get('joined', ''),
            'day_of_last_contract_extension': p.get('day_of_last_contract_extension', ''),
            'outfitter': p.get('outfitter', ''),
            'social_media': ';'.join(p.get('social_media') or []),
            'url': f"https://www.transfermarkt.co.uk{p.get('href', '')}",
        })
    existing_players = load_csv_existing(OUT / 'players.csv')
    player_id_map = {r['player_id']: r for r in existing_players if r.get('player_id')}
    for r in new_player_rows:
        pid = str(r.get('player_id', ''))
        if pid:
            if pid in player_id_map:
                old_row = player_id_map[pid]
                # Bewaar debut kolommen van bestaande rij
                for col in debut_cols:
                    if col in old_row and old_row[col]:
                        r[col] = old_row[col]
                # Bewaar marktwaarde als nieuwe rij geen waarde heeft
                for mv_col in ['market_value_in_eur', 'highest_market_value_in_eur']:
                    if not r.get(mv_col) and old_row.get(mv_col):
                        r[mv_col] = old_row[mv_col]
                # Bewaar naam/club-naam als nieuwe scrape ze niet kon vinden
                for name_col in ['name', 'first_name', 'last_name', 'current_club_name']:
                    if not r.get(name_col) and old_row.get(name_col):
                        r[name_col] = old_row[name_col]
                # Bewaar geboortedatum/leeftijd/lengte als de nieuwe scrape
                # ze niet kon vinden (bv. door een label-wijziging op TM) -
                # anders verliest een al-bekende speler deze data bij elke
                # herscrape i.p.v. gewoon niets bij te leren.
                for bio_col in ['date_of_birth', 'age', 'height_in_cm']:
                    if not r.get(bio_col) and old_row.get(bio_col):
                        r[bio_col] = old_row[bio_col]
            player_id_map[pid] = r
    merged_players = list(player_id_map.values())
    if merged_players:
        all_cols = list(merged_players[0].keys())
        for col in debut_cols + extra_player_cols:
            if col not in all_cols:
                all_cols.append(col)
        with open(OUT / 'players.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
            w.writeheader()
            for row in merged_players:
                w.writerow({k: row.get(k, '') for k in all_cols})
        print(f'players.csv: {len(merged_players)} rijen (was {len(existing_players)}, +{len(merged_players)-len(existing_players)} nieuw)')
    # ── OPTREDENS ──
    appearances = load_jsonl(RAW / 'appearances.json')
    new_app_rows = []
    for a in appearances:
        parent = a.get('parent') or {}
        player_id = extract_id(parent.get('href', ''))
        player_club_id = extract_id((parent.get('current_club') or {}).get('href', ''))
        result_raw = a.get('result')
        if isinstance(result_raw, dict): result_href = result_raw.get('href', '')
        elif isinstance(result_raw, str): result_href = result_raw
        else: result_href = ''
        game_id = extract_id(result_href)
        date = a.get('date', '')
        appearance_id = f"{player_id}_{date.replace('/', '')}" if player_id and date else ''
        min_raw = a.get('minutes_played', '') or ''
        try: minutes_played = int(str(min_raw).replace("'", "").strip())
        except: minutes_played = 0
        def card_count(val):
            if val is None or val == '' or val == 0: return 0
            return 1
        def safe_int(val):
            try: return int(val) if val != '' and val is not None else 0
            except: return 0
        new_app_rows.append({
            'appearance_id': appearance_id, 'game_id': game_id,
            'player_id': player_id, 'player_club_id': player_club_id,
            'date': date,
            'player_name': f"{parent.get('name', '')} {parent.get('last_name', '')}".strip(),
            'competition_id': a.get('competition_code', ''),
            'yellow_cards': card_count(a.get('yellow_cards')),
            'red_cards': card_count(a.get('red_cards')),
            'goals': safe_int(a.get('goals')),
            'assists': safe_int(a.get('assists')),
            'minutes_played': minutes_played,
            'position_in_game': str(a.get('position_in_game', '') or '').strip(),
        })
    existing_apps = load_csv_existing(OUT / 'appearances_existing.csv')
    app_id_map = {r['appearance_id']: r for r in existing_apps if r.get('appearance_id')}
    for r in new_app_rows:
        if r['appearance_id']:
            app_id_map[r['appearance_id']] = r
    merged_apps = list(app_id_map.values())
    if merged_apps:
        all_app_cols = list(merged_apps[0].keys())
        with open(OUT / 'appearances.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=all_app_cols, extrasaction='ignore')
            w.writeheader()
            for row in merged_apps:
                w.writerow({k: row.get(k, '') for k in all_app_cols})
        print(f'appearances.csv: {len(merged_apps)} rijen (was {len(existing_apps)}, +{len(merged_apps)-len(existing_apps)} nieuw)')
    # ── WEDSTRIJDEN ──
    games = load_jsonl(RAW / 'games.json')
    print(f"Games geladen: {len(games)}")
    new_game_rows = []
    for g in games:
        if g.get('home_club_id') or g.get('home_club_goals') is not None:
            new_game_rows.append({
                'game_id':         g.get('game_id', ''),
                'competition_id':  g.get('competition_id', ''),
                'season':          g.get('season', ''),
                'date':            g.get('date', ''),
                'home_club_id':    g.get('home_club_id', ''),
                'away_club_id':    g.get('away_club_id', ''),
                'home_club_goals': g.get('home_club_goals', ''),
                'away_club_goals': g.get('away_club_goals', ''),
                'home_club_name':  g.get('home_club_name', ''),
                'away_club_name':  g.get('away_club_name', ''),
                'stadium':         g.get('stadium', ''),
                'attendance':      g.get('attendance', ''),
                'url':             g.get('url', ''),
            })
        else:
            result = g.get('result', '') or ''
            try:
                home_goals, away_goals = result.split(':')
                home_goals = home_goals.strip(); away_goals = away_goals.strip()
            except: home_goals, away_goals = '', ''
            home_id = extract_id((g.get('home_club') or {}).get('href', ''))
            away_id = extract_id((g.get('away_club') or {}).get('href', ''))
            comp_id = (g.get('parent') or {}).get('country_code', '') or                   extract_id((g.get('parent') or {}).get('href', ''))
            game_id = g.get('game_id', '') or extract_id(g.get('href', ''))
            new_game_rows.append({
                'game_id':         game_id,
                'competition_id':  comp_id,
                'season':          g.get('season', '2025'),
                'date':            g.get('date', ''),
                'home_club_id':    home_id,
                'away_club_id':    away_id,
                'home_club_goals': home_goals,
                'away_club_goals': away_goals,
                'home_club_name':  g.get('home_club_name', ''),
                'away_club_name':  g.get('away_club_name', ''),
                'stadium':         g.get('stadium', ''),
                'attendance':      g.get('attendance', ''),
                'url':             f"https://www.transfermarkt.co.uk{g.get('href', '')}",
            })
    existing_games = load_csv_existing(OUT / 'games.csv')
    game_id_map = {r['game_id']: r for r in existing_games if r.get('game_id')}
    for r in new_game_rows:
        if r['game_id']:
            game_id_map[str(r['game_id'])] = r
    merged_games = list(game_id_map.values())
    if merged_games:
        with open(OUT / 'games.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(merged_games[0].keys()))
            w.writeheader(); w.writerows(merged_games)
        print(f'games.csv: {len(merged_games)} rijen (was {len(existing_games)}, +{len(merged_games)-len(existing_games)} nieuw)')
    def _fix_encoding(s):
        if not s: return s
        s = s.replace(chr(226)+chr(130)+chr(172), 'EUR')
        s = s.replace(chr(194), '')
        return s
    def club_name(v):
        if isinstance(v, dict):
            return v.get('clubName', '') or ''
        return v or ''
    def club_crest(v):
        # PATCH: de transferHistory-API geeft het clublogo rechtstreeks mee
        # (clubEmblem-1x/-2x) - betrouwbaarder dan matchen op clubnaam
        # (transfers.csv gebruikt afgekorte namen als "Man City"/"Dortmund"
        # die niet overeenkomen met clubs.csv's volledige namen).
        if isinstance(v, dict):
            return v.get('clubEmblem-1x', '') or v.get('clubEmblem', '') or ''
        return ''
    def club_country_flag(v):
        if isinstance(v, dict):
            return v.get('countryFlag', '') or ''
        return ''
    def club_href_id(v):
        if isinstance(v, dict):
            href = v.get('href', '') or ''
            parts = href.rstrip('/').split('/')
            if 'verein' in parts:
                return parts[parts.index('verein') + 1]
        return ''
    # ── TRANSFERS ──
    # Laad transfers: probeer transfers_raw.json (scraper) en transfers.json (bestaand)
    raw_transfers = load_jsonl(RAW / 'transfers_raw.json')
    if not raw_transfers:
        raw_transfers = load_jsonl(RAW / 'transfers.json')
    transfers_raw = raw_transfers
    new_transfer_rows = []
    for t in transfers_raw:
        player_id = str(t.get('player_id', ''))
        from_obj = t.get('from_club_name') or t.get('from') or t.get('fromClubName')
        to_obj = t.get('to_club_name') or t.get('to') or t.get('toClubName')
        # dcaribou formaat: transfer_date, from_club_name, to_club_name, transfer_fee, market_value_in_eur
        # scraper formaat: date/transferDate, from/fromClubName, to/toClubName, fee, mv
        new_transfer_rows.append({
            'player_id':                player_id,
            'transfer_date':            t.get('transfer_date', '') or t.get('date', '') or t.get('transferDate', ''),
            'transfer_season':          t.get('transfer_season', '') or t.get('season', ''),
            'from_club_name':           club_name(from_obj),
            'to_club_name':             club_name(to_obj),
            'from_club_id':             club_href_id(from_obj),
            'to_club_id':               club_href_id(to_obj),
            'from_club_crest_url':      club_crest(from_obj),
            'to_club_crest_url':        club_crest(to_obj),
            'to_country_flag_url':      club_country_flag(to_obj),
            'transfer_fee':             _fix_encoding(t.get('transfer_fee', '') or t.get('fee', '') or t.get('transferFee', '')),
            'market_value_at_transfer': _fix_encoding(t.get('market_value_in_eur', '') or t.get('mv', '') or t.get('marketValue', '')),
        })
    existing_transfers = load_csv_existing(OUT / 'transfers.csv')
    transfer_key = lambda r: f"{r.get('player_id','')}_{r.get('transfer_date','')}_{r.get('to_club_name','')}"
    transfer_map = {transfer_key(r): r for r in existing_transfers}
    for r in new_transfer_rows:
        key = transfer_key(r)
        old_row = transfer_map.get(key)
        if old_row:
            for keep_col in ['from_club_id', 'to_club_id', 'from_club_crest_url', 'to_club_crest_url', 'to_country_flag_url']:
                if not r.get(keep_col) and old_row.get(keep_col):
                    r[keep_col] = old_row[keep_col]
        transfer_map[key] = r
    merged_transfers = list(transfer_map.values())
    if merged_transfers:
        transfer_cols = [
            'player_id', 'transfer_date', 'transfer_season',
            'from_club_name', 'to_club_name', 'from_club_id', 'to_club_id',
            'from_club_crest_url', 'to_club_crest_url', 'to_country_flag_url',
            'transfer_fee', 'market_value_at_transfer',
        ]
        with open(OUT / 'transfers.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=transfer_cols, extrasaction='ignore')
            w.writeheader()
            for row in merged_transfers:
                w.writerow({k: row.get(k, '') for k in transfer_cols})
        print(f'transfers.csv: {len(merged_transfers)} rijen (was {len(existing_transfers)}, +{len(merged_transfers)-len(existing_transfers)} nieuw)')
    # ── VALUATIONS ──
    valuations_raw = load_jsonl(RAW / 'valuations.json')
    new_val_rows = []
    for v in valuations_raw:
        player_id = str(v.get('player_id', ''))
        mv_raw = v.get('market_value_in_eur', '') or v.get('market_value', '') or v.get('mw', '')
        new_val_rows.append({
            'player_id':           player_id,
            'date':                v.get('date', '') or v.get('datum_mw', ''),
            'date_timestamp':      v.get('date_timestamp', '') or v.get('date_x', ''),
            'market_value_in_eur': parse_market_value(str(mv_raw)) if mv_raw else '',
            'club_name':           v.get('club_name', '') or v.get('verein', ''),
            'age':                 v.get('age', ''),
        })
    existing_vals = load_csv_existing(OUT / 'player_valuations.csv')
    val_key = lambda r: f"{r.get('player_id','')}_{r.get('date','')}"
    val_map = {val_key(r): r for r in existing_vals}
    for r in new_val_rows:
        val_map[val_key(r)] = r
    merged_vals = list(val_map.values())
    if merged_vals:
        with open(OUT / 'player_valuations.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(merged_vals[0].keys()))
            w.writeheader(); w.writerows(merged_vals)
        print(f'player_valuations.csv: {len(merged_vals)} rijen (was {len(existing_vals)}, +{len(merged_vals)-len(existing_vals)} nieuw)')
    tmp = Path('data/csv/appearances_existing.csv')
    if tmp.exists(): tmp.unlink()
    print('Conversie en samenvoegen klaar!')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'decompress':
        decompress()
    elif cmd == 'merge':
        merge()
    else:
        print("Gebruik: merge_csv.py [decompress|merge]")
        sys.exit(1)
