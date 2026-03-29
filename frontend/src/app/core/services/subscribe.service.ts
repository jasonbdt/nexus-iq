import {Injectable, computed, signal, inject} from '@angular/core';
import {SummonerService} from './summoner.service';

export type StreamStatus = 'idle' | 'connecting' | 'open' | 'error';

export interface ConnectedEventPayload {
  status: 'connected';
  channel: string;
}

export interface GenericUpdatePayload {
  [key: string]: unknown;
}

const API_BASE = '/api/v1';

@Injectable({ providedIn: 'root' })
export class SubscribeService {
  public eventSource: EventSource | null = null;

  private readonly _status = signal<StreamStatus>('idle')
  private readonly _lastEventId = signal<string | null>(null);
  private readonly _connected = signal<ConnectedEventPayload | null>(null);
  private readonly _update = signal<GenericUpdatePayload | null>(null);
  private readonly _errorMessage = signal<string | null>(null);

  readonly status = this._status.asReadonly();
  readonly lastEvendId = this._lastEventId.asReadonly();
  readonly connected = this._connected.asReadonly();
  readonly update = this._update.asReadonly();
  readonly errorMessage = this._errorMessage.asReadonly();

  readonly isConnected = computed(() => this._status() === 'open');
  readonly hasError = computed(() => this._status() === 'error' && !!this._errorMessage());

  subscribeSummonerUpdates(puuid: string): void {
    if (!puuid) {
      this._status.set('error');
      this._errorMessage.set('Missing puuid')
      return;
    }

    this.disconnect({ resetState: false });

    this._status.set('connecting');
    this._errorMessage.set(null);
    this._lastEventId.set(null);
    this._connected.set(null);
    this._update.set(null);

    const url = `${API_BASE}/subscribe/${encodeURIComponent(puuid)}`;
    const es = new EventSource(url, { withCredentials: true });
    this.eventSource = es;

    es.onopen = (): void => {
      this._status.set('open');
      this._errorMessage.set(null);
    };

    es.onerror = (): void => {
      this._status.set('error');
      this._errorMessage.set('SSE connection error');
    }

    es.addEventListener('connected', (event: Event) => {
      const msg = event as MessageEvent<string>;
      this._status.set('open');
      this._lastEventId.set(msg.lastEventId || null);
      this._connected.set(this.parseJSON<ConnectedEventPayload>(msg.data));
      this._errorMessage.set(null);
    });

    // TODO: Remove this as its too generic
    es.addEventListener('update', (event: Event): void => {
      const msg = event as MessageEvent<string>;
      this._lastEventId.set(msg.lastEventId || null);
      this._update.set(this.parseJSON<GenericUpdatePayload>(msg.data));
    });
  }

  disconnect(options?: { resetState: boolean }): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null;
    }

    this._status.set('idle');

    if (options?.resetState ?? true) {
      this.resetState();
    }
  }

  private resetState(): void {
    this._lastEventId.set(null);
    this._connected.set(null);
    this._update.set(null);
    this._errorMessage.set(null);
  }

  private parseJSON<T>(raw: string): T {
    return JSON.parse(raw) as T;
  }
}
