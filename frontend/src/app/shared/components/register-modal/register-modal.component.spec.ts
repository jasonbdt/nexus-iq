import { TestBed } from '@angular/core/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { of, throwError } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../../core/services/auth.service';
import { SummonerService } from '../../../core/services/summoner.service';
import { RegisterModalComponent } from './register-modal.component';

describe('RegisterModalComponent with an unranked player', () => {
  const player = {
    puuid: 'p'.repeat(78), riot_id: 'Test Player#EUW', summoner_name: 'Test Player',
    tag_line: 'EUW', region: 'euw', summoner_level: 30, profile_icon: 1, leagues: [],
    revision_date: '', created_at: '', updated_at: '', status: 'idle',
  };
  let register: ReturnType<typeof vi.fn>;
  let search: ReturnType<typeof vi.fn>;
  let close: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    register = vi.fn(() => of({}));
    search = vi.fn(() => of(player));
    close = vi.fn();
    await TestBed.configureTestingModule({
      imports: [RegisterModalComponent],
      providers: [
        { provide: AuthService, useValue: { register } },
        { provide: SummonerService, useValue: { search } },
        { provide: MatDialogRef, useValue: { close } },
      ],
    }).compileComponents();
  });

  function setup() {
    const fixture = TestBed.createComponent(RegisterModalComponent);
    const component = fixture.componentInstance;
    component.credentialsForm.setValue({
      emailAddress: 'new@example.test', password: 'password-123', password_confirm: 'password-123',
    });
    component.submitCredentials();
    component.playerSearchForm.setValue({ gameName: 'Test Player', tagLine: 'EUW' });
    return fixture;
  }

  it('allows selecting an unranked player and completing registration', () => {
    const fixture = setup();
    const component = fixture.componentInstance;
    component.searchPlayer();
    fixture.detectChanges();
    expect(component.selectedSummoner()?.leagues).toEqual([]);
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('.submit-btn');
    expect(button.disabled).toBe(false);
    button.click();
    expect(register).toHaveBeenCalledWith(expect.objectContaining({
      gameName: 'Test Player', tagLine: 'EUW', emailAddress: 'new@example.test',
    }));
    expect(close).toHaveBeenCalledWith('registered');
  });

  it('keeps a failed search as an error and prevents registration', () => {
    search.mockReturnValue(throwError(() => new Error('upstream unavailable')));
    const fixture = setup();
    const component = fixture.componentInstance;
    component.searchPlayer();
    fixture.detectChanges();
    expect(component.searchError()).not.toBe('');
    expect(component.selectedSummoner()).toBeNull();
    component.finishRegistration();
    expect(register).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('.summoner-result')).toBeNull();
  });
});
