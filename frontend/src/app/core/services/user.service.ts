import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UserResponse, UsersListResponse } from '../models';

const API_BASE = '/api/v1';

@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly http = inject(HttpClient);

  getUsers(offset = 0, limit = 100): Observable<UsersListResponse> {
    const params = new HttpParams().set('offset', offset).set('limit', limit);
    return this.http.get<UsersListResponse>(`${API_BASE}/users`, { params });
  }

  getMe(): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${API_BASE}/users/me`);
  }

  getUserById(id: number): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${API_BASE}/users/${id}`);
  }

  deleteUser(id: number): Observable<{ status: number; message: string }> {
    return this.http.delete<{ status: number; message: string }>(`${API_BASE}/users/${id}`);
  }
}
