export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserSignUpRequest {
  avatarName: string;
  emailAddress: string;
  password: string;
  password_confirm: string;
  /** Required: link primary player account during registration */
  gameName: string;
  tagLine: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export type UserRole = 'administrator' | 'moderator' | 'paid_member' | 'member';

export interface LinkedSummonerInfo {
  puuid: string;
  riot_id: string;
  profile_icon: number;
  region: string;
  summoner_level: number;
  link_slot?: number;
  link_id?: number;
  linked_at?: string | null;
}

export interface UserResponse {
  avatarName: string;
  emailAddress: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
  updated_at: string;
  linked_summoner?: LinkedSummonerInfo | null;
  summoner_linked_at?: string | null;
  additional_summoners?: LinkedSummonerInfo[];
  language?: string;
  subscription_tier?: string;
}

export interface UsersListResponse {
  status: number;
  message: string;
  users: UserResponse[];
}
