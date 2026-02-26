import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RagQueryResponse } from '../models';

const API_BASE = '/api/v1';

export interface PatchEntry {
  version: string;
  url: string;
}

@Injectable({ providedIn: 'root' })
export class RagService {
  private readonly http = inject(HttpClient);

  query(question: string, topK = 5): Observable<RagQueryResponse> {
    const params = new HttpParams().set('question', question).set('top_k', topK);
    return this.http.post<RagQueryResponse>(`${API_BASE}/query`, null, { params });
  }

  /**
   * Stream a RAG query response via Server-Sent Events.
   * Yields each text delta as it arrives from the backend.
   * The caller should append deltas to the message content in real time.
   */
  async *queryStream(question: string, topK = 5): AsyncGenerator<string> {
    const url = `${API_BASE}/query/stream?question=${encodeURIComponent(question)}&top_k=${topK}`;
    const response = await fetch(url, { method: 'POST' });

    if (!response.ok || !response.body) {
      throw new Error(`Stream request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // Keep the last (potentially incomplete) line in the buffer
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

  listPatches(): Observable<{ patches: PatchEntry[] }> {
    return this.http.get<{ patches: PatchEntry[] }>(`${API_BASE}/patches`);
  }

  ingestPatch(patchVersion: string): Observable<{ message: string; count: number }> {
    return this.http.post<{ message: string; count: number }>(
      `${API_BASE}/ingest/${patchVersion}`,
      null,
    );
  }
}
