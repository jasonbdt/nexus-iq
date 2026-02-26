import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatSession } from '../models';

const API_BASE = '/api/v1/coach';

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
}

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
   * Stream an AI response for the given session via SSE.
   * Returns an AsyncGenerator yielding token deltas.
   * The backend persists both the user question and the completed assistant
   * reply automatically.
   */
  async *chatStream(sessionId: number, question: string, token: string): AsyncGenerator<string> {
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

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') return;
        try {
          const parsed = JSON.parse(payload) as { delta: string };
          if (parsed.delta) yield parsed.delta;
        } catch {
          // malformed line — skip
        }
      }
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
      })),
    };
  }
}
