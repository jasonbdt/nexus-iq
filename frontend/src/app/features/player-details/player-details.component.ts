import { ChangeDetectionStrategy, Component, computed, DestroyRef, effect, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';
import { SummonerService } from '../../core/services/summoner.service';
import { MatchService } from '../../core/services/match.service';
import { DdragonService } from '../../core/services/ddragon.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { AiChatWidgetComponent } from '../../shared/components/ai-chat-widget/ai-chat-widget.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';
import { MatchOverviewComponent } from '../../shared/components/match-overview/match-overview';
import { SummonerSearch, MatchesRead, LeagueEntry, Participant } from '../../core/models';
import { RefreshButtonComponent } from '../../shared/components/refresh-button/refresh-button.component';
import { SubscribeService } from '../../core/services/subscribe.service';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

@Component({
  selector: 'app-player-details',
  imports: [
    MatchOverviewComponent,
    RouterLink,
    MatTabsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    NavbarComponent,
    AiChatWidgetComponent,
    RefreshButtonComponent,
  ],
  templateUrl: './player-details.component.html',
  styleUrl: './player-details.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PlayerDetailsComponent implements OnInit {
  readonly stream = inject(SubscribeService);

  private readonly route = inject(ActivatedRoute);
  private readonly summonerService = inject(SummonerService);
  private readonly matchService = inject(MatchService);
  private readonly ddragon = inject(DdragonService);
  private readonly dialog = inject(MatDialog);
  private readonly snackbar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  readonly summoner = signal<SummonerSearch | null>(null);
  readonly matches = signal<MatchesRead[]>([]);
  readonly loadingSummoner = signal(true);
  readonly loadingMatches = signal(false);

  readonly summonerStatus = signal<string>("idle");
  readonly updateProgress = signal<number|undefined>(undefined);
  readonly updateInProgress = signal<{ [key: string]: unknown }>({});

  readonly error = signal('');

  readonly gameName = signal('');
  readonly tagLine = signal('');

  readonly avgKills = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0.0';
    return (ms.reduce((s, m) => s + (this.getPlayerParticipant(m)?.kills ?? 0), 0) / ms.length).toFixed(1);
  });

  readonly avgDeaths = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0.0';
    return (ms.reduce((s, m) => s + (this.getPlayerParticipant(m)?.deaths ?? 0), 0) / ms.length).toFixed(1);
  });

  readonly avgAssists = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0.0';
    return (ms.reduce((s, m) => s + (this.getPlayerParticipant(m)?.assists ?? 0), 0) / ms.length).toFixed(1);
  });

  readonly avgCs = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0';
    return (ms.reduce((s, m) => s + (this.getPlayerParticipant(m)?.total_cs ?? 0), 0) / ms.length).toFixed(0);
  });

  readonly avgVision = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0';
    return (ms.reduce((s, m) => s + (this.getPlayerParticipant(m)?.vision_score ?? 0), 0) / ms.length).toFixed(0);
  });

  readonly recentWinRate = computed(() => {
    const ms = this.matches();
    if (!ms.length) return '0';
    return (ms.filter((m) => this.didWin(m)).length / ms.length * 100).toFixed(0);
  });

  constructor() {
    effect((): void => {
      const summonerStatus = this.summonerStatus();

      if (summonerStatus) {
        if (summonerStatus === "queued") {
          this.snackbar.open("Summoner update has been queued.", "Dismiss", {
            panelClass: "custom-snackbar",
            duration: 5000
          })
        } else if (summonerStatus === "finished") {
          this.snackbar.open("Summoner update completed.", "Dismiss", {
            panelClass: "custom-snackbar",
            duration: 5000
          })
        }
      }
    });
  }

  ngOnInit(): void {
    this.route.params.subscribe((params) => {
      this.gameName.set(params['gameName']);
      this.tagLine.set(params['tagLine']);
      this.loadSummoner();
    });

    this.destroyRef.onDestroy(() => {
      this.stream.disconnect();
    });
  }

  private loadSummoner(): void {
    this.loadingSummoner.set(true);
    this.error.set('');

    this.summonerService.search(this.gameName(), this.tagLine()).subscribe({
      next: (data) => {
        this.summoner.set(data);
        this.loadingSummoner.set(false);

        if (data.status !== "idle") {
          this.summonerStatus.set(data.status);
          this.updateProgress.set(data.update_progress);
        }

        this.loadMatches(data);
        this.stream.subscribeSummonerUpdates(data.puuid)
        this.stream.eventSource!.addEventListener('toggleUpdate', (event: Event): void => {
          const msg = event as MessageEvent<string>;
          const data = JSON.parse(msg.data);
          this.updateInProgress.set(data);
          this.summonerStatus.set(data.status);
          this.updateProgress.set(data.progress);
        });

        this.stream.eventSource!.addEventListener('reloadMatchList', (): void => {
          this.loadMatches(data);
        });
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Player not found.');
        this.loadingSummoner.set(false);
      },
    });
  }

  private loadMatches(summoner: SummonerSearch): void {
    this.loadingMatches.set(true);
    this.matchService.getMatchesByPuuid(summoner.region, summoner.puuid, 10).subscribe({
      next: (data) => {
        this.matches.set(data);
        this.loadingMatches.set(false);
      },
      error: () => {
        this.loadingMatches.set(false);
      },
    });
  }

  refreshSummoner(): void {
    const s = this.summoner();
    if (!s || this.summonerStatus() !== "idle") return;
    this.summonerService.update(s.puuid).subscribe({
      next: () => {
        this.updateProgress.set(0);
      }
    });
  }

  getSoloQueue(): LeagueEntry | undefined {
    return this.summoner()?.leagues.find((l) => l.queue_type === 'RANKED_SOLO_5x5');
  }

  getFlexQueue(): LeagueEntry | undefined {
    return this.summoner()?.leagues.find((l) => l.queue_type === 'RANKED_FLEX_SR');
  }

  getPlayerParticipant(match: MatchesRead): Participant | undefined {
    for (const team of match.teams) {
      const p = team.participants.find(
        (part) => part.riot_id === `${this.gameName()}#${this.tagLine()}`,
      );
      if (p) return p;
    }
    return match.teams[0]?.participants[0];
  }

  didWin(match: MatchesRead): boolean {
    const participant = this.getPlayerParticipant(match);
    if (!participant) return false;
    const team = match.teams.find((t) =>
      t.participants.some((p) => p.champion_name === participant.champion_name),
    );
    return team?.win ?? false;
  }

  getGameDuration(match: MatchesRead): string {
    const mins = Math.floor(match.game_duration / 60);
    const secs = match.game_duration % 60;
    return `${mins}m ${secs}s`;
  }

  profileIconUrl(iconId: number): string {
    return this.ddragon.profileIconUrl(iconId);
  }

  getChampionIconUrl(championName: string): string {
    return this.ddragon.championImageUrl(championName);
  }

  getTopChampions(): Array<{ name: string; games: number; winRate: number; kda: number }> {
    const champMap = new Map<string, { wins: number; games: number; kills: number; deaths: number; assists: number }>();
    for (const match of this.matches()) {
      const p = this.getPlayerParticipant(match);
      if (!p) continue;
      const existing = champMap.get(p.champion_name) ?? { wins: 0, games: 0, kills: 0, deaths: 0, assists: 0 };
      existing.games++;
      if (this.didWin(match)) existing.wins++;
      existing.kills += p.kills;
      existing.deaths += p.deaths;
      existing.assists += p.assists;
      champMap.set(p.champion_name, existing);
    }
    return Array.from(champMap.entries())
      .map(([name, stats]) => ({
        name,
        games: stats.games,
        winRate: stats.games > 0 ? (stats.wins / stats.games) * 100 : 0,
        kda: stats.deaths > 0 ? (stats.kills + stats.assists) / stats.deaths : stats.kills + stats.assists,
      }))
      .sort((a, b) => b.games - a.games)
      .slice(0, 5);
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
