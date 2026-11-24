// Nederlandse labels voor de per-wedstrijd playerStats-velden, 1-op-1
// overgenomen van streamlit/fotmob.py's MATCH_STAT_LABELS_NL zodat beide
// apps dezelfde terminologie gebruiken.
export const MATCH_STAT_LABELS_NL: Record<string, string> = {
  "Accurate crosses": "Nauwkeurige voorzetten",
  "Accurate long balls": "Nauwkeurige lange passes",
  "Accurate passes": "Nauwkeurige passes",
  "Acted as sweeper": "Acties als sweeper-keeper",
  "Aerial duels won": "Luchtduels gewonnen",
  Assists: "Assists",
  "Big chances created": "Grote kansen gecreëerd",
  "Big chances missed": "Grote kansen gemist",
  "Blocked shots": "Geblokte schoten",
  Blocks: "Blocks",
  "Chances created": "Kansen gecreëerd",
  "Clearance off the line": "Clearance van de lijn",
  Clearances: "Clearances",
  "Conceded penalty": "Toegestane penalty",
  Corners: "Hoekschoppen",
  "Defensive actions": "Defensieve acties",
  Dispossessed: "Bal verloren onder druk",
  "Diving save": "Reddende duik",
  "Dribbled past": "Gepasseerd",
  "Duels lost": "Duels verloren",
  "Duels won": "Duels gewonnen",
  "Error led to goal": "Fout leidde tot goal",
  "Expected assists (xA)": "Verwachte assists (xA)",
  "Expected goals (xG)": "Verwachte goals (xG)",
  "Expected goals on target (xGOT)": "xG op doel (xGOT)",
  "FotMob rating": "FotMob-rapportcijfer",
  "Fouls committed": "Overtredingen",
  Goals: "Doelpunten",
  "Goals conceded": "Tegendoelpunten",
  "Goals prevented": "Doelpunten voorkomen",
  "Ground duels won": "Grondduels gewonnen",
  "Headed clearance": "Clearance met het hoofd",
  "High claim": "Hoge bal gevangen",
  "Hit woodwork": "Paal/lat geraakt",
  Interceptions: "Onderscheppingen",
  "Last man tackle": "Tackle als laatste man",
  "Line breaking passes": "Linie-doorbrekende passes",
  "Minutes played": "Minuten gespeeld",
  "Missed penalty": "Gemiste penalty",
  Offsides: "Buitenspel",
  "Own goal": "Eigen doelpunt",
  "Passes into final third": "Passes naar laatste derde",
  "Penalties won": "Uitgelokte penalty's",
  Punches: "Weggeboksde ballen",
  Recoveries: "Balveroveringen",
  "Saved penalties": "Gestopte penalty's",
  Saves: "Reddingen",
  "Saves inside box": "Reddingen in de zestien",
  "Shots off target": "Schoten naast",
  "Shots on target": "Schoten op doel",
  "Successful dribbles": "Geslaagde dribbels",
  Tackles: "Tackles",
  Throws: "Ingooien",
  "Total shots": "Totaal schoten",
  Touches: "Balcontacten",
  "Touches in opposition box": "Balcontacten in strafschopgebied",
  "Was fouled": "Gefouleerd",
  "xG Non-penalty": "xG zonder penalty's",
  "xGOT faced": "xGOT tegen",
};

export const MATCH_STAT_GROUP_LABELS_NL: Record<string, string> = {
  "Top stats": "Topstatistieken",
  Attack: "Aanval",
  Defense: "Verdediging",
  Duels: "Duels",
};

export const GROUP_ORDER = ["Top stats", "Attack", "Defense", "Duels"];

// Al als tegel getoond bovenaan - niet nog eens in de gedetailleerde tabel.
export const HEADLINE_STAT_NAMES = new Set([
  "Goals",
  "Assists",
  "FotMob rating",
  "Expected goals (xG)",
  "Expected assists (xA)",
  "Minutes played",
]);

export function statLabel(name: string): string {
  return MATCH_STAT_LABELS_NL[name] ?? name;
}
