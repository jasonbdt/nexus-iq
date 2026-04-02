export interface Ban {
  champion_id: number;
  pick_turn: number;
}

export interface Objective {
  objective: string;
  first: boolean;
  kills: number;
}

export interface Rune {
  primary_style: number;
  primary_perk0: number;
  primary_perk1: number;
  primary_perk2: number;
  primary_perk3: number;
  secondary_style: number;
  secondary_perk0: number;
  secondary_perk1: number;
  stat_perk_defense: number;
  stat_perk_flex: number;
  stat_perk_offense: number;
}

export interface ParticipantProfile {
  summoner_name: string;
  tag_line: string;
  riot_id: string;
}

export interface Participant {
  champion_id: number;
  champion_name: string;
  champion_level: number;
  summoner_name: string;
  spell_1: string;
  spell_2: string;
  primary_style: string;
  secondary_style: string;
  tag_line: string;
  riot_id: string;
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
  total_cs: number;
  gold_earned: number;
  vision_score: number;
  wards_placed: number;
  wards_killed: number;
  vision_wards_bought: number;
  item0: number;
  item1: number;
  item2: number;
  item3: number;
  item4: number;
  item5: number;
  item6: number;
  profile: ParticipantProfile;
  runes: Rune[];
}

export interface Team {
  team_id: number;
  win: boolean;
  bans: Ban[];
  objectives: Objective[];
  participants: Participant[];
}

export interface MatchesRead {
  match_id: string;
  platform: string;
  queue_id: number;
  game_mode: string;
  game_type: string;
  game_version: string;
  map_id: number;
  game_start: string;
  game_end: string;
  game_duration: number;
  teams: Team[];
}
