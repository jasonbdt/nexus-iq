import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SummonerSearch, SummonerUpdateQueued } from '../models';

const API_BASE = '/api/v1';

@Injectable({ providedIn: 'root' })
export class SummonerService {
  private readonly http = inject(HttpClient);

  search(gameName: string, tagLine: string): Observable<SummonerSearch> {
    const encodedTag = encodeURIComponent(tagLine.trim());
    const encodedName = encodeURIComponent(gameName.trim());
    return this.http.get<SummonerSearch>(`${API_BASE}/search/${encodedTag}/${encodedName}`);
  }

  update(puuid: string, matchCount = 100): Observable<SummonerUpdateQueued> {
    const params = new HttpParams().set('match_count', matchCount);
    return this.http.patch<SummonerUpdateQueued>(`${API_BASE}/update/${puuid}`, null, { params });
  }
}
