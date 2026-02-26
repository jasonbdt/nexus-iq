import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { TitleCasePipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { SettingsService } from '../../core/services/settings.service';
import { SummonerService } from '../../core/services/summoner.service';
import { DdragonService } from '../../core/services/ddragon.service';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';
import { PlayerSearchInputComponent } from '../../shared/components/player-search-input/player-search-input.component';
import { MatDialog } from '@angular/material/dialog';
import { UserResponse } from '../../core/models';
import { SummonerSearch } from '../../core/models';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const newPassword = control.get('new_password');
  const confirm = control.get('new_password_confirm');
  if (newPassword && confirm && newPassword.value !== confirm.value) {
    return { passwordMismatch: true };
  }
  return null;
}

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'ko', label: '한국어' },
  { value: 'zh', label: '中文' },
];

@Component({
  selector: 'app-settings',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    TitleCasePipe,
    NavbarComponent,
    PlayerSearchInputComponent,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent implements OnInit {
  protected readonly authService = inject(AuthService);
  private readonly settingsService = inject(SettingsService);
  private readonly summonerService = inject(SummonerService);
  private readonly ddragon = inject(DdragonService);
  private readonly fb = inject(FormBuilder);
  private readonly dialog = inject(MatDialog);

  readonly user = signal<UserResponse | null>(null);
  readonly loading = signal(false);
  readonly emailSuccess = signal(false);
  readonly passwordSuccess = signal(false);
  readonly linkSuccess = signal(false);
  readonly emailError = signal('');
  readonly passwordError = signal('');
  readonly linkError = signal('');
  readonly searchError = signal('');
  readonly additionalSearchError = signal('');
  readonly searchLoading = signal(false);
  readonly foundSummoner = signal<SummonerSearch | null>(null);
  readonly foundAdditionalSummoner = signal<SummonerSearch | null>(null);

  readonly hideCurrentPassword = signal(true);
  readonly hideNewPassword = signal(true);
  readonly hideNewPasswordConfirm = signal(true);

  readonly languages = LANGUAGES;

  readonly emailForm = this.fb.nonNullable.group({
    emailAddress: ['', [Validators.required, Validators.email]],
    current_password: ['', Validators.required],
  });

  readonly passwordForm = this.fb.nonNullable.group(
    {
      current_password: ['', Validators.required],
      new_password: ['', [Validators.required, Validators.minLength(8)]],
      new_password_confirm: ['', Validators.required],
    },
    { validators: passwordMatchValidator },
  );

  readonly languageForm = this.fb.nonNullable.group({
    language: ['en', Validators.required],
  });

  readonly playerSearchForm = this.fb.nonNullable.group({
    gameName: ['', Validators.required],
    tagLine: ['', Validators.required],
  });

  readonly additionalSearchForm = this.fb.nonNullable.group({
    gameName: ['', Validators.required],
    tagLine: ['', Validators.required],
  });

  ngOnInit(): void {
    const u = this.authService.currentUser();
    this.user.set(u);
    if (u?.language) {
      this.languageForm.patchValue({ language: u.language });
    }
  }

  get canChangeSummoner(): boolean {
    const u = this.user();
    if (!u?.summoner_linked_at) return true;
    const linkedAt = new Date(u.summoner_linked_at).getTime();
    const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
    return Date.now() - linkedAt >= thirtyDaysMs;
  }

  get daysUntilSummonerChange(): number {
    const u = this.user();
    if (!u?.summoner_linked_at || this.canChangeSummoner) return 0;
    const linkedAt = new Date(u.summoner_linked_at).getTime();
    const nextAllowed = linkedAt + 30 * 24 * 60 * 60 * 1000;
    return Math.max(0, Math.ceil((nextAllowed - Date.now()) / (24 * 60 * 60 * 1000)));
  }

  profileIconUrl(iconId: number): string {
    return this.ddragon.profileIconUrl(iconId);
  }

  updateEmail(): void {
    if (this.emailForm.invalid) return;
    this.loading.set(true);
    this.emailError.set('');
    this.emailSuccess.set(false);

    const { emailAddress, current_password } = this.emailForm.getRawValue();
    this.settingsService.updateProfile({ emailAddress, current_password }).subscribe({
      next: (updated) => {
        this.authService.setCurrentUser(updated);
        this.user.set(updated);
        this.loading.set(false);
        this.emailSuccess.set(true);
        this.emailForm.reset();
      },
      error: (err: { error?: { detail?: string } }) => {
        this.emailError.set(err?.error?.detail || 'Failed to update email');
        this.loading.set(false);
      },
    });
  }

  updatePassword(): void {
    if (this.passwordForm.invalid) return;
    this.loading.set(true);
    this.passwordError.set('');
    this.passwordSuccess.set(false);

    const { current_password, new_password } = this.passwordForm.getRawValue();
    this.settingsService.updateProfile({ current_password, new_password }).subscribe({
      next: () => {
        this.loading.set(false);
        this.passwordSuccess.set(true);
        this.passwordForm.reset();
      },
      error: (err: { error?: { detail?: string } }) => {
        this.passwordError.set(err?.error?.detail || 'Failed to update password');
        this.loading.set(false);
      },
    });
  }

  updateLanguage(): void {
    const lang = this.languageForm.get('language')?.value;
    if (!lang) return;
    this.settingsService.updateProfile({ language: lang }).subscribe({
      next: (updated) => {
        this.authService.setCurrentUser(updated);
        this.user.set(updated);
      },
    });
  }

  searchPlayerForPrimary(): void {
    if (this.playerSearchForm.invalid) return;
    const { gameName, tagLine } = this.playerSearchForm.getRawValue();
    this.searchLoading.set(true);
    this.searchError.set('');
    this.foundSummoner.set(null);
    this.foundAdditionalSummoner.set(null);

    this.summonerService.search(gameName, tagLine).subscribe({
      next: (s) => {
        this.foundSummoner.set(s);
        this.searchLoading.set(false);
      },
      error: () => {
        this.searchError.set('Player not found. Check the name and tag.');
        this.searchLoading.set(false);
      },
    });
  }

  searchPlayerForAdditional(): void {
    if (this.additionalSearchForm.invalid) return;
    const { gameName, tagLine } = this.additionalSearchForm.getRawValue();
    this.searchLoading.set(true);
    this.additionalSearchError.set('');
    this.foundAdditionalSummoner.set(null);
    this.foundSummoner.set(null);

    this.summonerService.search(gameName, tagLine).subscribe({
      next: (s) => {
        this.foundAdditionalSummoner.set(s);
        this.searchLoading.set(false);
      },
      error: () => {
        this.additionalSearchError.set('Player not found. Check the name and tag.');
        this.searchLoading.set(false);
      },
    });
  }

  linkSummoner(linkSlot: number): void {
    const s = this.foundSummoner();
    if (!s || linkSlot !== 0) return;

    this.loading.set(true);
    this.linkError.set('');
    this.linkSuccess.set(false);

    this.settingsService.linkSummoner({ gameName: s.summoner_name, tagLine: s.tag_line, link_slot: 0 }).subscribe({
      next: (updated) => {
        this.authService.setCurrentUser(updated);
        this.user.set(updated);
        this.foundSummoner.set(null);
        this.playerSearchForm.reset();
        this.loading.set(false);
        this.linkSuccess.set(true);
      },
      error: (err: { error?: { detail?: string } }) => {
        this.linkError.set(err?.error?.detail || 'Failed to link account');
        this.loading.set(false);
      },
    });
  }

  linkAdditionalSummoner(): void {
    const s = this.foundAdditionalSummoner();
    if (!s) return;

    const currentAdditional = this.user()?.additional_summoners ?? [];
    const nextSlot = currentAdditional.length < 1 ? 1 : 2;

    this.loading.set(true);
    this.linkError.set('');
    this.linkSuccess.set(false);

    this.settingsService.linkSummoner({ gameName: s.summoner_name, tagLine: s.tag_line, link_slot: nextSlot }).subscribe({
      next: (updated) => {
        this.authService.setCurrentUser(updated);
        this.user.set(updated);
        this.foundAdditionalSummoner.set(null);
        this.additionalSearchForm.reset();
        this.loading.set(false);
        this.linkSuccess.set(true);
      },
      error: (err: { error?: { detail?: string } }) => {
        this.linkError.set(err?.error?.detail || 'Failed to add account');
        this.loading.set(false);
      },
    });
  }

  removeAdditionalSummoner(linkId: number | undefined): void {
    if (linkId == null) return;

    this.loading.set(true);
    this.linkError.set('');
    this.linkSuccess.set(false);

    this.settingsService.removeSummonerLink(linkId).subscribe({
      next: (updated) => {
        this.authService.setCurrentUser(updated);
        this.user.set(updated);
        this.loading.set(false);
        this.linkSuccess.set(true);
      },
      error: (err: { error?: { detail?: string } }) => {
        this.linkError.set(err?.error?.detail || 'Failed to remove account');
        this.loading.set(false);
      },
    });
  }

  openLogin(): void {
    this.dialog.open(LoginModalComponent, { panelClass: 'nexus-dialog', backdropClass: 'nexus-backdrop' });
  }

  openRegister(): void {
    const ref = this.dialog.open(RegisterModalComponent, { panelClass: 'nexus-dialog', backdropClass: 'nexus-backdrop' });
    ref.afterClosed().subscribe((result) => {
      if (result === 'registered') this.openLogin();
    });
  }
}
