import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RagService } from '../../../core/services/rag.service';
import { ChatMessage } from '../../../core/models';

@Component({
  selector: 'app-ai-chat-widget',
  imports: [FormsModule, DatePipe, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './ai-chat-widget.component.html',
  styleUrl: './ai-chat-widget.component.scss',
})
export class AiChatWidgetComponent implements AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  private readonly ragService = inject(RagService);

  readonly isOpen = signal(false);
  readonly loading = signal(false);
  readonly inputText = signal('');
  readonly messages = signal<ChatMessage[]>([
    {
      role: 'assistant',
      content: "Hi! I'm your NexusIQ AI Coach. Ask me anything about League of Legends — patch notes, champion tips, strategies, and more!",
      timestamp: new Date(),
    },
  ]);

  private shouldScrollToBottom = false;

  toggleChat(): void {
    this.isOpen.update((v) => !v);
    if (this.isOpen()) {
      this.shouldScrollToBottom = true;
    }
  }

  sendMessage(): void {
    const text = this.inputText().trim();
    if (!text || this.loading()) return;

    this.messages.update((msgs) => [
      ...msgs,
      { role: 'user', content: text, timestamp: new Date() },
    ]);
    this.inputText.set('');
    this.loading.set(true);
    this.shouldScrollToBottom = true;

    this.ragService.query(text).subscribe({
      next: (res) => {
        this.messages.update((msgs) => [
          ...msgs,
          { role: 'assistant', content: res.message, timestamp: new Date() },
        ]);
        this.loading.set(false);
        this.shouldScrollToBottom = true;
      },
      error: () => {
        this.messages.update((msgs) => [
          ...msgs,
          {
            role: 'assistant',
            content: 'Sorry, I encountered an error. Please try again.',
            timestamp: new Date(),
          },
        ]);
        this.loading.set(false);
        this.shouldScrollToBottom = true;
      },
    });
  }

  clearChat(): void {
    this.messages.set([
      {
        role: 'assistant',
        content: "Chat cleared! How can I help you improve your game?",
        timestamp: new Date(),
      },
    ]);
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom && this.messagesContainer) {
      const el = this.messagesContainer.nativeElement;
      el.scrollTop = el.scrollHeight;
      this.shouldScrollToBottom = false;
    }
  }
}
