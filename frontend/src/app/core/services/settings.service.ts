import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UserResponse } from '../models';

const API_BASE = '/api/v1';

export interface UpdateProfilePayload {
  emailAddress?: string;
  current_password?: string;
  new_password?: string;
  language?: string;
}

export interface LinkSummonerPayload {
  gameName: string;
  tagLine: string;
  link_slot?: number; // 0=primary, 1-2=additional (Premium only)
}

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly http = inject(HttpClient);

  updateProfile(payload: UpdateProfilePayload): Observable<UserResponse> {
    const body: Record<string, string> = {};
    if (payload.emailAddress !== undefined) body['emailAddress'] = payload.emailAddress;
    if (payload.current_password !== undefined) body['current_password'] = payload.current_password;
    if (payload.new_password !== undefined) body['new_password'] = payload.new_password;
    if (payload.language !== undefined) body['language'] = payload.language;
    return this.http.patch<UserResponse>(`${API_BASE}/users/me`, body);
  }

  linkSummoner(payload: LinkSummonerPayload): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${API_BASE}/users/me/link-summoner`, payload);
  }

  removeSummonerLink(linkId: number): Observable<UserResponse> {
    return this.http.delete<UserResponse>(`${API_BASE}/users/me/summoner-links/${linkId}`);
  }
}
