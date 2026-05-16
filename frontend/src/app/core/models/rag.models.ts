export interface RagQueryResponse {
  message: string;
}

export interface RagIngestResponse {
  message: string;
  count: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  streaming?: boolean;
  /** Model reasoning summary, shown in the meta row while streaming (not persisted). */
  reasoningSummary?: string;
  /** Seconds from request start until first answer token (assistant only). */
  thoughtSeconds?: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: ChatMessage[];
}
