import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatSession } from '../models';

const API_BASE = '/api/v1/coach';

/** Discriminated events from coach SSE (backend-driven labels). */
export type CoachStreamEvent =
  | { kind: 'status'; step: string; label: string; progress?: number | null }
  | { kind: 'reasoning'; text: string }
  | { kind: 'token'; text: string }
  | { kind: 'error'; message: string; step?: string }
  | { kind: 'done'; label?: string };

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly http = inject(HttpClient);

  listSessions(): Observable<ApiSession[]> {
    return this.http.get<ApiSession[]>(`${API_BASE}/sessions`);
  }

  createSession(title = 'New Session'): Observable<ApiSession> {
    return this.http.post<ApiSession>(`${API_BASE}/sessions`, { title });
  }

  getSession(id: number): Observable<ApiSession> {
    return this.http.get<ApiSession>(`${API_BASE}/sessions/${id}`);
  }

  renameSession(id: number, title: string): Observable<ApiSession> {
    return this.http.patch<ApiSession>(`${API_BASE}/sessions/${id}`, { title });
  }

  deleteSession(id: number): Observable<void> {
    return this.http.delete<void>(`${API_BASE}/sessions/${id}`);
  }

  /**
   * Stream coach pipeline events (status, tokens, done, error) via SSE.
   */
  async *chatStream(sessionId: number, question: string, token: string): AsyncGenerator<CoachStreamEvent> {
    const url = `${API_BASE}/sessions/${sessionId}/chat?question=${encodeURIComponent(question)}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok || !response.body) {
      throw new Error(`Chat stream failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let pendingEvent = 'message';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          pendingEvent = line.slice(6).trim();
          continue;
        }
        if (!line.startsWith('data:')) continue;
        const raw = line.slice(5).trim();
        if (raw === '[DONE]') {
          yield { kind: 'done', label: 'Done' };
          return;
        }
        try {
          const data = JSON.parse(raw) as Record<string, unknown>;
          const ev = this.mapSseToEvent(pendingEvent, data);
          if (ev) yield ev;
        } catch {
          /* skip malformed frame */
        }
      }
    }
  }

  private mapSseToEvent(eventName: string, data: Record<string, unknown>): CoachStreamEvent | null {
    switch (eventName) {
      case 'status':
        return {
          kind: 'status',
          step: String(data['step'] ?? ''),
          label: String(data['label'] ?? ''),
          progress: data['progress'] === undefined ? undefined : (data['progress'] as number | null),
        };
      case 'reasoning':
        return { kind: 'reasoning', text: String(data['text'] ?? '') };
      case 'token':
        return { kind: 'token', text: String(data['text'] ?? '') };
      case 'error':
        return {
          kind: 'error',
          message: String(data['message'] ?? 'Unknown error'),
          step: data['step'] !== undefined ? String(data['step']) : undefined,
        };
      case 'done':
        return { kind: 'done', label: data['label'] !== undefined ? String(data['label']) : undefined };
      default:
        return null;
    }
  }

  /** Convert an API session (with string dates) into the frontend ChatSession model. */
  static toFrontend(s: ApiSession): ChatSession {
    return {
      id: String(s.id),
      title: s.title,
      createdAt: new Date(s.created_at),
      updatedAt: new Date(s.updated_at),
      messages: s.messages.map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: new Date(m.created_at),
        thoughtSeconds: m.thought_seconds ?? undefined,
      })),
    };
  }
}

export interface ApiSession {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ApiMessage[];
}

export interface ApiMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  /** Present for assistant messages after server-side stream timing. */
  thought_seconds?: number | null;
}
