export interface LeagueEntry {
  league_id: string;
  queue_type: string;
  tier: string;
  rank: string;
  wins: number;
  losses: number;
  league_points: number;
  total_games: number;
  win_rate: number;
}

export interface SummonerSearch {
  puuid: string;
  region: string;
  summoner_name: string;
  tag_line: string;
  riot_id: string;
  summoner_level: number;
  profile_icon: number;
  leagues: LeagueEntry[];
  status: string;
  update_progress?: number;
  revision_date: string;
  created_at: string;
  updated_at: string;
}

export interface SummonerUpdateQueued {
  message: string
}
