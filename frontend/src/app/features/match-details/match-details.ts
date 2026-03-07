import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatchService } from '../../core/services/match.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { MatchOverviewComponent } from '../../shared/components/match-overview/match-overview';

@Component({
  selector: 'app-match-details',
  imports: [
    RouterLink,
    MatProgressSpinnerModule,
    MatButtonModule,
    MatIconModule,
    NavbarComponent,
    MatchOverviewComponent,
  ],
  templateUrl: './match-details.html',
  styleUrl: './match-details.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MatchDetailsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly matchService = inject(MatchService);

  readonly match = signal<import('../../core/models').MatchesRead | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  readonly focalRiotId = signal<string | undefined>(undefined);

  ngOnInit(): void {
    this.route.params.subscribe((params) => {
      const region = params['region'];
      const matchId = params['matchId'];
      if (!region || !matchId) {
        this.error.set('Invalid match URL');
        this.loading.set(false);
        return;
      }
      const riotId = this.route.snapshot.queryParamMap.get('focal') ?? undefined;
      this.focalRiotId.set(riotId ?? undefined);
      this.loadMatch(region, matchId);
    });
  }

  private loadMatch(region: string, matchId: string): void {
    this.loading.set(true);
    this.error.set('');
    this.matchService.getMatchById(region, matchId).subscribe({
      next: (data) => {
        this.match.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Match not found');
        this.loading.set(false);
      },
    });
  }
}
