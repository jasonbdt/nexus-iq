import { Component, output, signal, WritableSignal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { Subject } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/services/auth.service';
import { MatchService } from '../../core/services/match.service';
import { SummonerService } from '../../core/services/summoner.service';
import { SummonerSearch } from '../../core/models';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { DashboardComponent } from './dashboard.component';

@Component({ selector: 'app-navbar', template: '' })
class NavbarStub {
  readonly openLogin = output<void>();
  readonly openRegister = output<void>();
}

describe('Dashboard ranked states', () => {
  let response: Subject<SummonerSearch>;
  let user: WritableSignal<{ linked_summoner: { riot_id: string } } | null>;
  let search: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    response = new Subject<SummonerSearch>();
    user = signal({ linked_summoner: { riot_id: 'Test Player#EUW' } });
    search = vi.fn(() => response);
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser: user, isAdministrator: () => false } },
        { provide: SummonerService, useValue: { search } },
        { provide: MatchService, useValue: {} },
        { provide: MatDialog, useValue: {} },
      ],
    }).overrideComponent(DashboardComponent, {
      remove: { imports: [NavbarComponent] }, add: { imports: [NavbarStub] },
    }).compileComponents();
  });

  function setup() {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    return fixture;
  }

  function player(leagues: SummonerSearch['leagues'] = []): SummonerSearch {
    return {
      puuid: 'p'.repeat(78), region: 'euw', summoner_name: 'Test Player', tag_line: 'EUW',
      riot_id: 'Test Player#EUW', summoner_level: 30, profile_icon: 1, leagues,
      revision_date: '', created_at: '', updated_at: '', status: 'idle',
    };
  }

  it('shows loading until a profile arrives, then Unranked for an empty ranked list', () => {
    const fixture = setup();
    expect(fixture.nativeElement.textContent).toContain('Loading rank data');
    expect(fixture.nativeElement.textContent).not.toContain('Unranked');
    response.next(player());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Unranked');
    expect(fixture.nativeElement.textContent).not.toContain('Link your League');
  });

  it('shows actual Solo/Duo rank when present', () => {
    const fixture = setup();
    response.next(player([{
      queue_type: 'RANKED_SOLO_5x5', tier: 'GOLD', rank: 'II', league_points: 45,
      wins: 12, losses: 8, total_games: 20, win_rate: 60,
    }]));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('GOLD II');
    expect(fixture.nativeElement.textContent).not.toContain('Unranked');
  });

  it('shows Unranked for Solo/Duo when only Flex is ranked', () => {
    const fixture = setup();
    response.next(player([{
      queue_type: 'RANKED_FLEX_SR', tier: 'GOLD', rank: 'II', league_points: 45,
      wins: 12, losses: 8, total_games: 20, win_rate: 60,
    }]));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Unranked');
  });

  it('shows a load error rather than Unranked or the account-link hint', () => {
    const fixture = setup();
    response.error(new Error('upstream unavailable'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent)
      .toContain('Unable to load ranked data');
    expect(fixture.nativeElement.textContent).not.toContain('Unranked');
    expect(fixture.nativeElement.textContent).not.toContain('Link your League');
  });

  it('asks users without a linked account to link one', () => {
    user.set(null);
    const fixture = setup();
    expect(search).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Link your League');
    expect(fixture.nativeElement.textContent).not.toContain('Unranked');
  });
});
