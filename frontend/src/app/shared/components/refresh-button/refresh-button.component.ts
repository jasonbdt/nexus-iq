import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
} from '@angular/core';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

/** Stable IDs for [@progressLayer]. */
export const RefreshProgressState = {
  idle: 'idle',
  active: 'active',
} as const;

const EASING_DECEL = 'cubic-bezier(0.05, 0.7, 0.1, 1)';
const EASING_ACCEL = 'cubic-bezier(0.3, 0, 0.8, 0.15)';

const progressLayerTrigger = trigger('progressLayer', [
  state(RefreshProgressState.idle, style({ opacity: 0 })),
  state(RefreshProgressState.active, style({ opacity: 1 })),
  transition(`${RefreshProgressState.idle} => ${RefreshProgressState.active}`, [
    animate(`200ms ${EASING_DECEL}`),
  ]),
  transition(`${RefreshProgressState.active} => ${RefreshProgressState.idle}`, [
    animate(`250ms ${EASING_ACCEL}`),
  ]),
]);

/** Enter/leave when swapping idle vs busy label via @if. */
const labelSwapTrigger = trigger('labelSwap', [
  transition(':enter', [
    style({ opacity: 0, transform: 'translateY(6px)' }),
    animate(
      `200ms ${EASING_DECEL}`,
      style({ opacity: 1, transform: 'translateY(0)' }),
    ),
  ]),
  transition(':leave', [
    animate(
      `150ms ${EASING_ACCEL}`,
      style({ opacity: 0, transform: 'translateY(-4px)' }),
    ),
  ]),
]);

@Component({
  selector: 'app-refresh-button',
  imports: [MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './refresh-button.component.html',
  styleUrl: './refresh-button.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  animations: [progressLayerTrigger, labelSwapTrigger],
})
export class RefreshButtonComponent {
  readonly updating = input<string>("idle");
  readonly progress = input<number|undefined>(0);
  readonly disabled = input(false);

  readonly refresh = output<void>();

  readonly progressPercent = computed(() =>
    Math.min(100, Math.max(0, Math.round(this.progress() ?? 0))),
  );

  readonly progressFillWidth = computed(() =>
    this.updating() ? this.progressPercent() : 0,
  );

  readonly isActionDisabled = computed(
    () => this.disabled() || this.updating() !== "idle",
  );

  readonly progressLayer = computed(() =>
    this.updating() ? RefreshProgressState.active : RefreshProgressState.idle,
  );

  readonly ariaLabel = computed(() =>
    this.updating()
      ? `Updating match data, ${this.progressPercent()} percent complete`
      : 'Update summoner match data',
  );

  protected onClick(): void {
    if (this.disabled() || this.updating() !== "idle") return;
    this.refresh.emit();
  }
}
