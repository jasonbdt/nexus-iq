import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, firstValueFrom } from 'rxjs';
import { Token, UserSignUpRequest, UserResponse, UserRole } from '../models';

const API_BASE = '/api/v1';
const TOKEN_KEY = 'nexusiq_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly _token = signal<string | null>(this.loadToken());
  private readonly _currentUser = signal<UserResponse | null>(null);
  /** True once initializeAuth() has finished its /users/me call (or skipped it). */
  private readonly _initialized = signal(false);

  readonly token = this._token.asReadonly();
  readonly currentUser = this._currentUser.asReadonly();
  readonly isLoggedIn = computed(() => !!this._token());
  readonly initialized = this._initialized.asReadonly();

  /** Role decoded directly from the JWT payload — available immediately without an HTTP call. */
  readonly role = computed<UserRole | null>(() => {
    const t = this._token();
    if (!t) return null;
    try {
      const payload = JSON.parse(atob(t.split('.')[1]));
      return (payload['role'] as UserRole) ?? null;
    } catch {
      return null;
    }
  });

  readonly isAdministrator = computed(() => this.role() === 'administrator');
  readonly isModerator = computed(() => this.role() === 'moderator' || this.isAdministrator());
  readonly isPaidMember = computed(
    () => this.role() === 'paid_member' || this.isModerator(),
  );

  private loadToken(): string | null {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(TOKEN_KEY);
    }
    return null;
  }

  login(username: string, password: string): Observable<Token> {
    const body = new HttpParams().set('username', username).set('password', password);
    return this.http
      .post<Token>(`${API_BASE}/login`, body.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      .pipe(
        tap((token) => {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(TOKEN_KEY, token.access_token);
          }
          this._token.set(token.access_token);
          this.loadCurrentUser();
        }),
      );
  }

  register(payload: UserSignUpRequest): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${API_BASE}/register`, payload);
  }

  loadCurrentUser(): void {
    if (!this._token()) return;
    this.http.get<UserResponse>(`${API_BASE}/users/me`).subscribe({
      next: (user) => {
        this._currentUser.set(user);
        this._initialized.set(true);
      },
      error: () => this.logout(),
    });
  }

  /** Update current user from an API response (e.g. after settings update). */
  setCurrentUser(user: UserResponse | null): void {
    this._currentUser.set(user);
  }

  logout(): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY);
    }
    this._token.set(null);
    this._currentUser.set(null);
    this._initialized.set(true); // unblock any waiting guards
    this.router.navigate(['/']);
  }

  /**
   * Called once at app startup. Returns a Promise so it can be used as an
   * APP_INITIALIZER, ensuring guards never run before the user profile is loaded.
   */
  async initializeAuth(): Promise<void> {
    if (!this._token()) {
      this._initialized.set(true);
      return;
    }
    try {
      const user = await firstValueFrom(
        this.http.get<UserResponse>(`${API_BASE}/users/me`),
      );
      this._currentUser.set(user);
    } catch {
      // Token is invalid / expired — clear it silently
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(TOKEN_KEY);
      }
      this._token.set(null);
      this._currentUser.set(null);
    } finally {
      this._initialized.set(true);
    }
  }
}
