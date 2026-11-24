const API_BASE = "http://localhost:8000";

export interface PlayerSummary {
  player_id: number;
  name: string;
  position: string | null;
  current_club_id: number | null;
  current_club_name: string | null;
  current_club_crest_url: string | null;
  current_club_domestic_competition_id?: string | null;
  market_value_in_eur: number | null;
  date_of_birth: string | null;
  age: string | null;
  foot?: string | null;
  height_in_cm?: number | null;
  contract_expiration_date?: string | null;
  country_of_citizenship: string | null;
  country_of_citizenship_flag_url: string | null;
  image_url: string | null;
}

export interface PlayerSearchResult {
  total: number;
  items: PlayerSummary[];
}

export interface Transfer {
  transfer_date: string;
  transfer_season: string;
  from_club_name: string;
  to_club_name: string;
  from_club_crest_url: string | null;
  to_club_crest_url: string | null;
  transfer_fee: string | null;
  market_value_at_transfer: string | null;
}

export interface Injury {
  season: string;
  injury: string;
  from_date: string;
  until_date: string;
  days: number | null;
  games_missed: number | null;
}

export interface Appearance {
  appearance_id: number;
  date: string;
  competition_id: string;
  goals: number;
  assists: number;
  minutes_played: number;
  yellow_cards: number;
  red_cards: number;
}

export interface Valuation {
  date: string;
  market_value_in_eur: number;
  club_name: string | null;
  club_crest_url: string | null;
}

export interface PlayerDetail {
  player: Record<string, unknown> & PlayerSummary;
  transfers: Transfer[];
  valuations: Valuation[];
  injuries: Injury[];
  appearances: Appearance[];
}

export interface ClubSummary {
  club_id: number;
  name: string;
  domestic_competition_id: string;
  squad_size: number | null;
  average_age: number | null;
  total_market_value: string | null;
  crest_url: string | null;
  stadium_name: string | null;
}

export interface ClubDetail {
  club: ClubSummary & Record<string, unknown>;
  squad: PlayerSummary[];
}

export interface Competition {
  competition_id: string;
  name: string;
  country: string;
  tier: string;
  flag_url: string | null;
  logo_url: string | null;
  club_count: number;
}

export interface FotmobLeague {
  key: string;
  label: string;
}

export interface FotmobStanding {
  group_name: string | null;
  team_id: number;
  name: string;
  idx: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  scores_str: string;
  goal_con_diff: number;
  pts: number;
}

export interface FotmobLeaderboardRow {
  fotmob_id?: number;
  team_id: number;
  name: string;
  value: number;
  rank: number;
}

export interface FotmobShot {
  x: number;
  y: number;
  event_type: string;
  expected_goals: number;
  minute: number;
  situation: string | null;
  shot_type: string | null;
}

export interface FotmobStatEntry {
  group: string;
  value: number;
}

export interface FotmobPlayerMatch {
  matched: boolean;
  league_key?: string;
  league_label?: string;
  fotmob_name?: string;
  matches_played?: number;
  totals?: Record<string, FotmobStatEntry>;
  percentiles?: Record<string, number>;
  shots?: FotmobShot[];
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API-fout (${res.status}) bij ${path}`);
  }
  return res.json() as Promise<T>;
}

export type SortOrder = "asc" | "desc";

export interface PlayerFilters {
  q?: string;
  position?: string;
  nationality?: string;
  foot?: string;
  competitionId?: string;
  minAge?: number;
  maxAge?: number;
  minValue?: number;
  maxValue?: number;
}

export function searchPlayers(
  filters: PlayerFilters,
  sort: string = "market_value",
  order: SortOrder = "desc",
  limit = 50,
): Promise<PlayerSearchResult> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.position) params.set("position", filters.position);
  if (filters.nationality) params.set("nationality", filters.nationality);
  if (filters.foot) params.set("foot", filters.foot);
  if (filters.competitionId) params.set("competition_id", filters.competitionId);
  if (filters.minAge != null) params.set("min_age", String(filters.minAge));
  if (filters.maxAge != null) params.set("max_age", String(filters.maxAge));
  if (filters.minValue != null) params.set("min_value", String(filters.minValue * 1_000_000));
  if (filters.maxValue != null) params.set("max_value", String(filters.maxValue * 1_000_000));
  params.set("sort", sort);
  params.set("order", order);
  params.set("limit", String(limit));
  return getJson(`/api/players?${params.toString()}`);
}

export interface NamedCount {
  name: string;
  count: number;
}

export function listNationalities(): Promise<NamedCount[]> {
  return getJson("/api/players/meta/nationalities");
}

export function listFeet(): Promise<string[]> {
  return getJson("/api/players/meta/feet");
}

export function getPlayer(playerId: number): Promise<PlayerDetail> {
  return getJson(`/api/players/${playerId}`);
}

export function listClubs(
  competitionId?: string,
  sort: string = "market_value",
  order: SortOrder = "desc",
): Promise<ClubSummary[]> {
  const params = new URLSearchParams();
  params.set("sort", sort);
  params.set("order", order);
  if (competitionId) params.set("competition_id", competitionId);
  return getJson(`/api/clubs?${params.toString()}`);
}

export function getClub(clubId: number): Promise<ClubDetail> {
  return getJson(`/api/clubs/${clubId}`);
}

export function listCompetitions(): Promise<Competition[]> {
  return getJson("/api/competitions");
}

export function listFotmobLeagues(): Promise<FotmobLeague[]> {
  return getJson("/api/fotmob/leagues");
}

export function getFotmobStandings(leagueKey: string): Promise<FotmobStanding[]> {
  return getJson(`/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/standings`);
}

export function getFotmobPlayerStatKeys(leagueKey: string): Promise<string[]> {
  return getJson(`/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/player-stat-keys`);
}

export function getFotmobPlayerMatch(playerId: number): Promise<FotmobPlayerMatch> {
  return getJson(`/api/fotmob/player-match/${playerId}`);
}

export function getFotmobPlayerStats(
  leagueKey: string,
  stat: string,
): Promise<FotmobLeaderboardRow[]> {
  return getJson(
    `/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/player-stats?stat=${encodeURIComponent(stat)}`,
  );
}

export function getFotmobTeamStatKeys(leagueKey: string): Promise<string[]> {
  return getJson(`/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/team-stat-keys`);
}

export function getFotmobTeamStats(leagueKey: string, stat: string): Promise<FotmobLeaderboardRow[]> {
  return getJson(
    `/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/team-stats?stat=${encodeURIComponent(stat)}`,
  );
}

export interface FotmobMatch {
  match_id: number;
  round: string | null;
  date: string | null;
  home_id: number;
  home_name: string;
  away_id: number;
  away_name: string;
  score: string | null;
  finished: boolean;
}

export function getFotmobMatches(leagueKey: string): Promise<FotmobMatch[]> {
  return getJson(`/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/matches`);
}

export interface FotmobMatchTeam {
  id: number;
  name: string;
  image_url: string | null;
  color: string;
}

export interface FotmobMatchTopStat {
  title: string;
  home: number | string;
  away: number | string;
}

export interface FotmobLineupPlayer {
  shirt_number: number | null;
  name: string;
  rating: number | null;
}

export interface FotmobLineupTeam {
  name: string;
  formation: string;
  starters: FotmobLineupPlayer[];
  subs: string[];
}

export interface FotmobMatchShot extends FotmobShot {
  player_id: number | null;
  player_name: string;
  team_id: number;
}

export interface FotmobMatchDetail {
  home: FotmobMatchTeam;
  away: FotmobMatchTeam;
  score_str: string;
  status_reason: string;
  top_stats: FotmobMatchTopStat[];
  momentum: { minute: number; value: number }[];
  lineup: { home: FotmobLineupTeam; away: FotmobLineupTeam };
  shots: FotmobMatchShot[];
}

export function getFotmobMatchDetail(leagueKey: string, matchId: number): Promise<FotmobMatchDetail> {
  return getJson(`/api/fotmob/leagues/${encodeURIComponent(leagueKey)}/matches/${matchId}`);
}

export interface PotentialCandidate {
  player_id: number;
  name: string;
  age: string | null;
  position: string | null;
  current_club_name: string | null;
  current_club_crest_url: string | null;
  competition_display: string | null;
  country: string | null;
  market_value_in_eur: number | null;
  recent_matches: number;
  recent_avg_minutes: number;
  recent_goals: number;
  recent_assists: number;
  minutes_trend: number;
  scoring_trend: number;
  just_broke_through: boolean;
}

export function getPotentialCandidates(
  maxAge = 23,
  recentDays = 30,
  minRecentMatches = 2,
): Promise<PotentialCandidate[]> {
  const params = new URLSearchParams({
    max_age: String(maxAge),
    recent_days: String(recentDays),
    min_recent_matches: String(minRecentMatches),
  });
  return getJson(`/api/potential?${params.toString()}`);
}

export interface CompareSeasonTotals {
  matches: number;
  goals: number;
  assists: number;
  minutes: number;
}

export interface ComparePlayer extends PlayerSummary {
  season_totals: CompareSeasonTotals;
}

export interface CompareResult {
  players: ComparePlayer[];
  valuations: { player_id: number; date: string; market_value_in_eur: number }[];
}

export function comparePlayers(ids: number[]): Promise<CompareResult> {
  return getJson(`/api/compare?ids=${ids.join(",")}`);
}

export interface ContractSignal {
  player_id: number;
  name: string;
  age: string | null;
  position: string | null;
  current_club_name: string | null;
  current_club_crest_url: string | null;
  country: string | null;
  contract_expiration_date: string;
  market_value_in_eur: number | null;
  competition_display: string | null;
}

export function getExpiringContracts(months = 6): Promise<ContractSignal[]> {
  return getJson(`/api/signals/contracts?months=${months}`);
}

export interface ValueChangeSignal {
  player_id: number;
  name: string;
  age: string | null;
  position: string | null;
  current_club_name: string | null;
  current_club_crest_url: string | null;
  competition_display: string | null;
  country: string | null;
  country_of_citizenship_flag_url: string | null;
  market_value_in_eur_toen: number;
  market_value_in_eur_nu: number;
  verandering_pct: number;
}

export function getValueChanges(
  monthsBack = 6,
  direction: "up" | "down" = "up",
  limit = 20,
): Promise<ValueChangeSignal[]> {
  const params = new URLSearchParams({ months_back: String(monthsBack), direction, limit: String(limit) });
  return getJson(`/api/signals/value-changes?${params.toString()}`);
}
