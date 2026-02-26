import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';
import { AuthService } from '../../core/services/auth.service';
import { DdragonService } from '../../core/services/ddragon.service';
import { SummonerService } from '../../core/services/summoner.service';
import { MatchService } from '../../core/services/match.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';
import { SummonerSearch, MatchesRead, LeagueEntry } from '../../core/models';

@Component({
  selector: 'app-dashboard',
  imports: [
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  protected readonly authService = inject(AuthService);
  protected readonly ddragon = inject(DdragonService);
  private readonly summonerService = inject(SummonerService);
  private readonly matchService = inject(MatchService);
  private readonly dialog = inject(MatDialog);

  readonly summoner = signal<SummonerSearch | null>(null);
  readonly recentMatches = signal<MatchesRead[]>([]);
  readonly loadingSummoner = signal(false);
  readonly loadingMatches = signal(false);

  readonly soloQueue = signal<LeagueEntry | null>(null);
  readonly flexQueue = signal<LeagueEntry | null>(null);

  readonly trainingPlan = [
    { task: '3 SoloQ games focusing on CS/min', done: false, icon: 'sports_esports' },
    { task: '2 VOD reviews of recent losses', done: false, icon: 'play_circle' },
    { task: '1 custom game for mechanics practice', done: false, icon: 'build' },
  ];

  readonly recentSessions = [
    { topic: 'Mid & Late Game Decision Making', duration: '32 min', icon: 'psychology' },
    { topic: 'Champion Pool Optimization', duration: '18 min', icon: 'star' },
    { topic: 'Laning Phase Fundamentals', duration: '25 min', icon: 'school' },
  ];

  ngOnInit(): void {
    const user = this.authService.currentUser();
    const linked = user?.linked_summoner;
    if (linked?.riot_id) {
      const hashIdx = linked.riot_id.indexOf('#');
      const gameName = hashIdx >= 0 ? linked.riot_id.slice(0, hashIdx) : linked.riot_id;
      const tagLine = hashIdx >= 0 ? linked.riot_id.slice(hashIdx + 1) : '';
      if (gameName && tagLine) {
        this.loadingSummoner.set(true);
        this.summonerService.search(gameName, tagLine).subscribe({
          next: (s) => {
            this.summoner.set(s);
            this.loadingSummoner.set(false);
          },
          error: () => this.loadingSummoner.set(false),
        });
      }
    }
  }

  getSoloQueue() {
    return this.summoner()?.leagues.find((l) => l.queue_type === 'RANKED_SOLO_5x5');
  }

  getFlexQueue() {
    return this.summoner()?.leagues.find((l) => l.queue_type === 'RANKED_FLEX_SR');
  }

  playerProfileLink(): string[] | null {
    const s = this.summoner();
    if (!s) return null;
    return ['/player', s.summoner_name, s.tag_line];
  }

  getWinRate(league: LeagueEntry): string {
    const pct = league.win_rate > 1 ? league.win_rate : league.win_rate * 100;
    return pct.toFixed(1);
  }

  getRankDisplay(league: LeagueEntry): string {
    return `${league.tier} ${league.rank}`;
  }

  getGameDurationMinutes(match: MatchesRead): number {
    return Math.floor(match.game_duration / 60);
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
      if (result === 'registered') {
        this.openLogin();
      }
    });
  }
}
