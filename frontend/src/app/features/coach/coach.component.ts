import {
  Component,
  ElementRef,
  inject,
  NgZone,
  OnInit,
  signal,
  ViewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { AuthService } from '../../core/services/auth.service';
import { ChatService } from '../../core/services/chat.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';
import { MatDialog } from '@angular/material/dialog';
import { MarkdownComponent } from 'ngx-markdown';
import { ChatMessage, ChatSession } from '../../core/models';

const SUGGESTED_QUESTIONS = [
  'What are the biggest changes in the latest patch?',
  'Which champions were buffed this patch?',
  'What items were nerfed recently?',
  'Which ADCs are strong in the current meta?',
  'How does the new drake affect gameplay?',
  'What changed for jungle in the latest patch?',
];

@Component({
  selector: 'app-coach',
  imports: [
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MarkdownComponent,
    NavbarComponent,
  ],
  templateUrl: './coach.component.html',
  styleUrl: './coach.component.scss',
})
export class CoachComponent implements OnInit {
  @ViewChild('chatMessages') private chatMessages!: ElementRef<HTMLElement>;

  protected readonly authService = inject(AuthService);
  private readonly chatService = inject(ChatService);
  private readonly dialog = inject(MatDialog);
  private readonly zone = inject(NgZone);

  readonly sessions = signal<ChatSession[]>([]);
  readonly activeSessionId = signal<string | null>(null);
  readonly inputText = signal('');
  readonly loading = signal(false);
  /** Pipeline step label for the in-flight assistant turn (plain text above the reply bubble). */
  readonly pipelineStatus = signal<string | null>(null);
  readonly loadingSessions = signal(false);
  readonly loadingMessages = signal(false);
  readonly suggestedQuestions = SUGGESTED_QUESTIONS;

  get activeSession(): ChatSession | null {
    const id = this.activeSessionId();
    return this.sessions().find((s) => s.id === id) ?? null;
  }

  ngOnInit(): void {
    this.loadSessions();
  }

  // ── Session management ────────────────────────────────────────────────────

  loadSessions(): void {
    this.loadingSessions.set(true);
    this.chatService.listSessions().subscribe({
      next: (apiSessions) => {
        const sessions = apiSessions.map(ChatService.toFrontend);
        this.sessions.set(sessions);
        this.loadingSessions.set(false);
        // Auto-select the most recent session, or create a fresh one
        if (sessions.length > 0) {
          this.selectSession(sessions[0].id);
        } else {
          this.newSession();
        }
      },
      error: () => {
        this.loadingSessions.set(false);
        this.newSession();
      },
    });
  }

  newSession(): void {
    this.chatService.createSession().subscribe({
      next: (apiSession) => {
        const session = ChatService.toFrontend(apiSession);
        this.sessions.update((s) => [session, ...s]);
        this.activeSessionId.set(session.id);
      },
      error: () => {
        // Fallback: create a local-only session so the UI stays usable
        const local: ChatSession = {
          id: crypto.randomUUID(),
          title: 'New Session',
          createdAt: new Date(),
          updatedAt: new Date(),
          messages: [],
        };
        this.sessions.update((s) => [local, ...s]);
        this.activeSessionId.set(local.id);
      },
    });
  }

  selectSession(id: string): void {
    if (this.loading()) return;
    if (this.activeSessionId() === id) return;

    this.activeSessionId.set(id);

    // Load full message history if not already present
    const session = this.sessions().find((s) => s.id === id);
    const numericId = Number(id);
    if (!session || isNaN(numericId)) return;

    // Only fetch if messages haven't been loaded yet
    if (session.messages.length === 0) {
      this.loadingMessages.set(true);
      this.chatService.getSession(numericId).subscribe({
        next: (apiSession) => {
          const loaded = ChatService.toFrontend(apiSession);
          this.sessions.update((sessions) =>
            sessions.map((s) => (s.id === id ? loaded : s)),
          );
          this.loadingMessages.set(false);
          this.scrollToBottom();
        },
        error: () => this.loadingMessages.set(false),
      });
    } else {
      this.scrollToBottom();
    }
  }

  deleteSession(id: string, event: MouseEvent): void {
    event.stopPropagation();
    const numericId = Number(id);
    if (!isNaN(numericId)) {
      this.chatService.deleteSession(numericId).subscribe();
    }

    const remaining = this.sessions().filter((s) => s.id !== id);
    this.sessions.set(remaining);

    if (this.activeSessionId() === id) {
      if (remaining.length > 0) {
        this.selectSession(remaining[0].id);
      } else {
        this.newSession();
      }
    }
  }

  // ── Messaging ─────────────────────────────────────────────────────────────

  sendMessage(): void {
    const text = this.inputText().trim();
    if (!text || this.loading()) return;

    const session = this.activeSession;
    if (!session) return;

    const numericId = Number(session.id);
    if (isNaN(numericId)) return;

    // Append user message to local state immediately
    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date() };
    this.updateSessionMessages(session.id, (msgs) => [...msgs, userMsg]);

    // Update title from first user message
    if (session.messages.length === 0) {
      const title = text.length > 80 ? text.slice(0, 80) + '…' : text;
      this.updateSessionTitle(session.id, title);
      this.chatService.renameSession(numericId, title).subscribe();
    }

    this.inputText.set('');
    this.pipelineStatus.set(null);
    this.loading.set(true);
    this.scrollToBottom();

    // Append streaming placeholder
    const assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      streaming: true,
    };
    this.updateSessionMessages(session.id, (msgs) => [...msgs, assistantMsg]);
    this.scrollToBottom();

    this.runStream(session.id, numericId, text);
  }

  private async runStream(sessionId: string, numericId: number, question: string): Promise<void> {
    const token = this.authService.token() ?? '';
    const streamStartedAt = Date.now();
    try {
      for await (const ev of this.chatService.chatStream(numericId, question, token)) {
        this.zone.run(() => {
          if (ev.kind === 'status') {
            this.pipelineStatus.set(ev.label);
          } else if (ev.kind === 'reasoning' && ev.text) {
            this.updateLastAssistantReasoning(sessionId, ev.text);
            this.scrollToBottom();
          } else if (ev.kind === 'token' && ev.text) {
            this.updateLastAssistantMessage(
              sessionId,
              (prev) => prev + ev.text,
              streamStartedAt,
            );
            this.scrollToBottom();
          } else if (ev.kind === 'error') {
            this.updateLastAssistantMessage(sessionId, () => ev.message, streamStartedAt);
            this.pipelineStatus.set(null);
          }
        });
      }
      this.zone.run(() => {
        const thoughtSeconds = Math.max(1, Math.round((Date.now() - streamStartedAt) / 1000));
        this.finalizeAssistantMessage(sessionId, thoughtSeconds);
        this.pipelineStatus.set(null);
        this.loading.set(false);
        this.scrollToBottom();
      });
    } catch {
      this.zone.run(() => {
        const thoughtSeconds = Math.max(1, Math.round((Date.now() - streamStartedAt) / 1000));
        this.updateLastAssistantMessage(
          sessionId,
          () => 'Sorry, I encountered an error. Please try again.',
          streamStartedAt,
        );
        this.finalizeAssistantMessage(sessionId, thoughtSeconds);
        this.pipelineStatus.set(null);
        this.loading.set(false);
      });
    }
  }

  askSuggested(question: string): void {
    this.inputText.set(question);
    this.sendMessage();
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private updateSessionMessages(
    id: string,
    updater: (msgs: ChatMessage[]) => ChatMessage[],
  ): void {
    this.sessions.update((sessions) =>
      sessions.map((s) =>
        s.id === id
          ? { ...s, messages: updater(s.messages), updatedAt: new Date() }
          : s,
      ),
    );
  }

  private updateLastAssistantReasoning(sessionId: string, textDelta: string): void {
    this.sessions.update((sessions) =>
      sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const msgs = [...s.messages];
        const lastIdx = msgs.length - 1;
        if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
          const prev = msgs[lastIdx].reasoningSummary ?? '';
          msgs[lastIdx] = {
            ...msgs[lastIdx],
            reasoningSummary: prev + textDelta,
          };
        }
        return { ...s, messages: msgs, updatedAt: new Date() };
      }),
    );
  }

  private updateSessionTitle(id: string, title: string): void {
    this.sessions.update((sessions) =>
      sessions.map((s) => (s.id === id ? { ...s, title } : s)),
    );
  }

  private updateLastAssistantMessage(
    sessionId: string,
    contentUpdater: (prev: string) => string,
    streamStartedAt?: number,
  ): void {
    this.sessions.update((sessions) =>
      sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const msgs = [...s.messages];
        const lastIdx = msgs.length - 1;
        if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
          const prevMsg = msgs[lastIdx];
          const prev = prevMsg.content;
          const newContent = contentUpdater(prev);
          let nextThought = prevMsg.thoughtSeconds;
          if (
            streamStartedAt != null &&
            nextThought == null &&
            prev === '' &&
            newContent !== ''
          ) {
            nextThought = Math.max(1, Math.round((Date.now() - streamStartedAt) / 1000));
          }
          msgs[lastIdx] = {
            ...prevMsg,
            content: newContent,
            ...(nextThought != null ? { thoughtSeconds: nextThought } : {}),
          };
        }
        return { ...s, messages: msgs, updatedAt: new Date() };
      }),
    );
  }

  private finalizeAssistantMessage(sessionId: string, fallbackThoughtSeconds?: number): void {
    this.sessions.update((sessions) =>
      sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const msgs = s.messages.map((m) => {
          if (!m.streaming) return m;
          const thoughtSeconds = m.thoughtSeconds ?? fallbackThoughtSeconds;
          return {
            ...m,
            streaming: false,
            reasoningSummary: undefined,
            ...(thoughtSeconds != null ? { thoughtSeconds } : {}),
          };
        });
        return { ...s, messages: msgs };
      }),
    );
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      if (this.chatMessages) {
        const el = this.chatMessages.nativeElement;
        el.scrollTop = el.scrollHeight;
      }
    }, 0);
  }

  // ── Dialog helpers (navbar) ───────────────────────────────────────────────

  openLogin(): void {
    this.dialog.open(LoginModalComponent, {
      panelClass: 'nexus-dialog',
      backdropClass: 'nexus-backdrop',
    });
  }

  openRegister(): void {
    const ref = this.dialog.open(RegisterModalComponent, {
      panelClass: 'nexus-dialog',
      backdropClass: 'nexus-backdrop',
    });
    ref.afterClosed().subscribe((result) => {
      if (result === 'registered') this.openLogin();
    });
  }
}
