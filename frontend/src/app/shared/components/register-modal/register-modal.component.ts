import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../../core/services/auth.service';
import { DdragonService } from '../../../core/services/ddragon.service';
import { SummonerService } from '../../../core/services/summoner.service';
import { SummonerSearch } from '../../../core/models';
import { PlayerSearchInputComponent } from '../player-search-input/player-search-input.component';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password');
  const confirm = control.get('password_confirm');
  if (password && confirm && password.value !== confirm.value) {
    return { passwordMismatch: true };
  }
  return null;
}

@Component({
  selector: 'app-register-modal',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    PlayerSearchInputComponent,
  ],
  templateUrl: './register-modal.component.html',
  styleUrl: './register-modal.component.scss',
})
export class RegisterModalComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  protected readonly ddragon = inject(DdragonService);
  private readonly summonerService = inject(SummonerService);
  private readonly dialogRef = inject(MatDialogRef<RegisterModalComponent>);

  /** 1 = credentials, 2 = link player account */
  readonly step = signal<1 | 2>(1);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly hidePassword = signal(true);
  readonly hideConfirm = signal(true);

  // Step 2 — player search
  readonly searchLoading = signal(false);
  readonly searchError = signal('');
  readonly foundSummoner = signal<SummonerSearch | null>(null);
  readonly selectedSummoner = signal<SummonerSearch | null>(null);

  readonly credentialsForm = this.fb.nonNullable.group(
    {
      emailAddress: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      password_confirm: ['', Validators.required],
    },
    { validators: passwordMatchValidator },
  );

  readonly playerSearchForm = this.fb.nonNullable.group({
    gameName: ['', Validators.required],
    tagLine: ['', Validators.required],
  });

  // ── Step 1 ──────────────────────────────────────────────────────────────────

  submitCredentials(): void {
    if (this.credentialsForm.invalid) return;
    this.step.set(2);
    this.error.set('');
  }

  // ── Step 2 ──────────────────────────────────────────────────────────────────

  searchPlayer(): void {
    if (this.playerSearchForm.invalid) return;
    const { gameName, tagLine } = this.playerSearchForm.getRawValue();
    this.searchLoading.set(true);
    this.searchError.set('');
    this.foundSummoner.set(null);
    this.selectedSummoner.set(null);

    this.summonerService.search(gameName, tagLine).subscribe({
      next: (s) => {
        this.foundSummoner.set(s);
        this.selectedSummoner.set(s); // Auto-select single result
        this.searchLoading.set(false);
      },
      error: () => {
        this.searchError.set('Player not found. Check the name and tag (e.g. Faker / KR1).');
        this.searchLoading.set(false);
      },
    });
  }

  selectSummoner(s: SummonerSearch): void {
    this.selectedSummoner.set(s);
  }

  finishRegistration(): void {
    const summoner = this.selectedSummoner();
    if (!summoner) return;

    const { emailAddress, password, password_confirm } = this.credentialsForm.getRawValue();
    this.loading.set(true);
    this.error.set('');

    this.authService
      .register({
        avatarName: summoner.riot_id,
        emailAddress,
        password,
        password_confirm,
        gameName: summoner.summoner_name,
        tagLine: summoner.tag_line,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.dialogRef.close('registered');
        },
        error: (err: { error?: { detail?: string } }) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail || 'Registration failed. Please try again.');
          this.step.set(1);
        },
      });
  }

  back(): void {
    this.step.set(1);
    this.error.set('');
    this.searchError.set('');
    this.foundSummoner.set(null);
    this.selectedSummoner.set(null);
  }

  close(): void {
    this.dialogRef.close();
  }
}
