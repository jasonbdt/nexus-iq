import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { DdragonService } from '../../../core/services/ddragon.service';
import { MatchesRead, Participant } from '../../../core/models';

const PLATFORM_TO_REGION: Record<string, string> = {
  NA1: 'americas',
  BR1: 'americas',
  LA1: 'americas',
  LA2: 'americas',
  EUW1: 'europe',
  EUN1: 'europe',
  TR1: 'europe',
  RU: 'europe',
  KR: 'asia',
  JP1: 'asia',
  OC1: 'sea',
  PH2: 'sea',
  SG2: 'sea',
  TH2: 'sea',
  TW2: 'sea',
  VN2: 'sea',
};

@Component({
  selector: 'app-match-overview',
  imports: [DatePipe],
  templateUrl: './match-overview.html',
  styleUrl: './match-overview.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[attr.role]': 'clickable() ? "button" : null',
    '[attr.tabindex]': 'clickable() ? "0" : null',
    '[attr.aria-label]': 'clickable() ? ariaLabel() : null',
    '[class.clickable]': 'clickable()',
    '(click)': 'handleClick()',
    '(keydown.enter)': 'handleClick()',
    '(keydown.space)': 'handleKeydown($event)',
  },
})
export class MatchOverviewComponent {
  readonly match = input.required<MatchesRead>();
  readonly currentPlayerRiotId = input<string>();
  readonly clickable = input(true);

  private readonly router = inject(Router);
  private readonly ddragon = inject(DdragonService);

  readonly participant = computed(() => {
    const m = this.match();
    const riotId = this.currentPlayerRiotId();
    if (riotId) {
      for (const team of m.teams) {
        const p = team.participants.find((part) => part.riot_id === riotId);
        if (p) return p;
      }
    }
    return m.teams[0]?.participants[0];
  });

  private readonly effectiveRiotId = computed(() => {
    const id = this.currentPlayerRiotId();
    if (id) return id;
    const p = this.participant();
    return p?.profile.riot_id ?? '';
  });

  readonly won = computed(() => {
    const p = this.participant();
    if (!p) return false;
    const m = this.match();
    const team = m.teams.find((t) =>
      t.participants.some((part) => part.champion_name === p.champion_name)
    );
    return team?.win ?? false;
  });

  readonly killParticipation = computed(() => {
    const p = this.participant();
    const m = this.match();
    if (!p) return 0;
    const team = m.teams.find((t) =>
      t.participants.some((part) => part.riot_id === this.effectiveRiotId())
    );
    if (!team) return 0;
    const teamKills = team.participants.reduce((s, part) => s + part.kills, 0);
    if (teamKills === 0) return 100;
    return Math.round(((p.kills + p.assists) / teamKills) * 100);
  });

  readonly purchasedItems = computed(() => {
    const p = this.participant();
    if (!p) return [];
    const ids = [p.item0, p.item1, p.item2, p.item3, p.item4, p.item5, p.item6];
    return ids.filter((id) => id && id > 0);
  });

  readonly otherParticipants = computed(() => {
    const m = this.match();
    const riotId = this.effectiveRiotId();
    const all: Participant[] = [];
    for (const team of m.teams) {
      for (const p of team.participants) {
        if (p.riot_id !== riotId) all.push(p);
      }
    }
    return all;
  });

  readonly ariaLabel = computed(() => {
    const p = this.participant();
    const w = this.won();
    const m = this.match();
    const champ = p?.champion_name ?? 'Unknown';
    const outcome = w ? 'Victory' : 'Defeat';
    const duration = this.getGameDuration(m);
    return `${champ} ${outcome}, ${duration}. View match details`;
  });

  getChampionIconUrl(championName: string): string {
    return this.ddragon.championImageUrl(championName ?? 'Jinx');
  }

  itemImageUrl(itemId: number): string {
    return this.ddragon.itemImageUrl(itemId);
  }

  getGameDuration(m: MatchesRead): string {
    const mins = Math.floor(m.game_duration / 60);
    const secs = m.game_duration % 60;
    return `${mins}m ${secs}s`;
  }

  getRegionFromPlatform(platform: string): string {
    return PLATFORM_TO_REGION[platform?.toUpperCase() ?? ''] ?? 'europe';
  }

  handleClick(): void {
    if (this.clickable()) this.navigateToMatchDetails();
  }

  handleKeydown(event: Event): void {
    const e = event as KeyboardEvent;
    if (this.clickable() && e.key === ' ') {
      e.preventDefault();
      this.navigateToMatchDetails();
    }
  }

  navigateToMatchDetails(): void {
    const m = this.match();
    const region = this.getRegionFromPlatform(m.platform);
    const riotId = this.effectiveRiotId();
    const queryParams = riotId ? { focal: riotId } : {};
    this.router.navigate(['/match', region, m.match_id], { queryParams });
  }
}
