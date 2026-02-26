import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';
import { DatePipe, NgClass } from '@angular/common';
import { UserService } from '../../core/services/user.service';
import { RagService, PatchEntry } from '../../core/services/rag.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';
import { UserResponse } from '../../core/models';

export interface IngestLogEntry {
  patchVersion: string;
  status: 'success' | 'error' | 'loading';
  message: string;
  chunkCount?: number;
  timestamp: Date;
}

@Component({
  selector: 'app-admin',
  imports: [
    FormsModule,
    NgClass,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatFormFieldModule,
    MatInputModule,
    MatTooltipModule,
    NavbarComponent,
    DatePipe,
  ],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss',
})
export class AdminComponent implements OnInit {
  private readonly userService = inject(UserService);
  private readonly ragService = inject(RagService);
  private readonly dialog = inject(MatDialog);

  readonly users = signal<UserResponse[]>([]);
  readonly loadingUsers = signal(true);
  readonly maintenanceMode = signal(false);
  readonly deletingUserId = signal<string | null>(null);
  readonly activeUsersCount = computed(() => this.users().filter((u) => u.is_active).length);

  // ── RAG Training ──────────────────────────────────────────────────────────
  readonly patchInput = signal('');
  readonly ingestLoading = signal(false);
  readonly ingestLog = signal<IngestLogEntry[]>([]);
  readonly availablePatches = signal<PatchEntry[]>([]);
  readonly loadingPatches = signal(false);

  loadPatches(): void {
    this.loadingPatches.set(true);
    this.ragService.listPatches().subscribe({
      next: (res) => {
        this.availablePatches.set(res.patches);
        this.loadingPatches.set(false);
      },
      error: () => {
        this.loadingPatches.set(false);
      },
    });
  }

  selectPatch(version: string): void {
    const current = this.patchInput().trim();
    if (!current) {
      this.patchInput.set(version);
      return;
    }
    // Append to existing comma-separated list if not already present
    const existing = current.split(',').map((v) => v.trim());
    if (!existing.includes(version)) {
      this.patchInput.set([...existing, version].join(', '));
    }
  }

  parsedVersions(): string[] {
    return this.patchInput()
      .split(',')
      .map((v) => v.trim())
      .filter((v) => /^\d+\.\d+$/.test(v));
  }

  isPatchVersionValid(): boolean {
    return this.parsedVersions().length > 0;
  }

  ingestPatch(): void {
    const versions = this.parsedVersions();
    if (versions.length === 0) return;

    this.ingestLoading.set(true);

    // Add a loading entry for every version upfront
    const now = new Date();
    const newEntries: IngestLogEntry[] = versions.map((v) => ({
      patchVersion: v,
      status: 'loading' as const,
      message: 'Scraping patch notes and generating embeddings…',
      timestamp: now,
    }));
    this.ingestLog.update((log) => [...newEntries, ...log]);
    this.patchInput.set('');

    // Ingest sequentially so the log updates one-by-one
    const ingestNext = (index: number): void => {
      if (index >= versions.length) {
        this.ingestLoading.set(false);
        return;
      }
      const version = versions[index];
      // The loading entries were prepended in order, so entry at position `index`
      // corresponds to versions[index] in the current log head.
      this.ragService.ingestPatch(version).subscribe({
        next: (res) => {
          this.ingestLog.update((log) =>
            log.map((entry) =>
              entry.patchVersion === version && entry.status === 'loading'
                ? { ...entry, status: 'success' as const, message: res.message, chunkCount: res.count }
                : entry,
            ),
          );
          ingestNext(index + 1);
        },
        error: (err: { error?: { message?: string } }) => {
          const msg = err?.error?.message || 'Failed to ingest patch notes. Check that the patch version exists.';
          this.ingestLog.update((log) =>
            log.map((entry) =>
              entry.patchVersion === version && entry.status === 'loading'
                ? { ...entry, status: 'error' as const, message: msg }
                : entry,
            ),
          );
          ingestNext(index + 1);
        },
      });
    };

    ingestNext(0);
  }

  clearIngestLog(): void {
    this.ingestLog.set([]);
  }

  readonly recentTickets = [
    { id: '#1042', user: 'player123', subject: 'Match history not loading', status: 'open', time: '2h ago' },
    { id: '#1041', user: 'gamer456', subject: 'AI coach not responding', status: 'in_progress', time: '4h ago' },
    { id: '#1040', user: 'summoner789', subject: 'Account verification issue', status: 'resolved', time: '1d ago' },
  ];

  readonly recentAiSessions = [
    { user: 'player123', topic: 'Champion pool advice', timestamp: new Date(Date.now() - 3600000), flagged: false },
    { user: 'gamer456', topic: 'Ranked strategy', timestamp: new Date(Date.now() - 7200000), flagged: true },
    { user: 'summoner789', topic: 'Patch 14.2 changes', timestamp: new Date(Date.now() - 86400000), flagged: false },
  ];

  ngOnInit(): void {
    this.loadUsers();
    this.loadPatches();
  }

  loadUsers(): void {
    this.loadingUsers.set(true);
    this.userService.getUsers().subscribe({
      next: (res) => {
        this.users.set(res.users);
        this.loadingUsers.set(false);
      },
      error: () => {
        this.loadingUsers.set(false);
      },
    });
  }

  deleteUser(email: string): void {
    // In a real app, we'd look up the user ID from the email
    // For now, just show the action
    console.log('Delete user:', email);
  }

  toggleMaintenance(): void {
    this.maintenanceMode.update((v) => !v);
  }

  getTicketStatusClass(status: string): string {
    const map: Record<string, string> = {
      open: 'status-open',
      in_progress: 'status-progress',
      resolved: 'status-resolved',
    };
    return map[status] ?? '';
  }

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
