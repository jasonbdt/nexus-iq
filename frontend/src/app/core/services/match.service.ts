import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { MatchesRead } from '../models';

const API_BASE = '/api/v1';

@Injectable({ providedIn: 'root' })
export class MatchService {
  private readonly http = inject(HttpClient);

  getMatchesByPuuid(region: string, puuid: string, matchCount = 10): Observable<MatchesRead[]> {
    const params = new HttpParams().set('match_count', matchCount);
    return this.http.get<MatchesRead[]>(`${API_BASE}/matches/${region}/by-puuid/${puuid}`, {
      params,
    });
  }

  getMatchById(region: string, matchId: string): Observable<MatchesRead> {
    return this.http.get<MatchesRead>(`${API_BASE}/matches/${region}/by-id/${matchId}`);
  }
}
