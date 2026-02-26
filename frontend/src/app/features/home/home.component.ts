import { Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatDialog } from '@angular/material/dialog';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { LoginModalComponent } from '../../shared/components/login-modal/login-modal.component';
import { RegisterModalComponent } from '../../shared/components/register-modal/register-modal.component';

@Component({
  selector: 'app-home',
  imports: [
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    NavbarComponent,
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);

  readonly gameName = signal('');
  readonly tagLine = signal('');
  readonly searchError = signal('');
  private readonly tagInputRef = viewChild<ElementRef<HTMLInputElement>>('tagInputRef');

  readonly features = [
    {
      icon: 'bar_chart',
      title: 'Stats Tracking',
      description: 'Deep dive into your performance metrics, win rates, KDA, and champion mastery across all ranked games.',
    },
    {
      icon: 'smart_toy',
      title: 'AI Coaching',
      description: 'Get personalized coaching from our AI powered by the latest patch notes and pro-level strategies.',
    },
    {
      icon: 'trending_up',
      title: 'Performance Analysis',
      description: 'Identify your weaknesses, track improvement over time, and get actionable tips to climb the ladder.',
    },
  ];

  onUnifiedInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const value = input.value;
    if (value.includes('#')) {
      const [name, tag] = value.split('#');
      input.value = name; // Remove # from name field immediately
      this.gameName.set(name);
      this.tagLine.set(tag);
      setTimeout(() => this.tagInputRef()?.nativeElement?.focus(), 0);
    } else {
      this.gameName.set(value);
    }
  }

  search(): void {
    const name = this.gameName().trim();
    const tag = this.tagLine().trim();
    if (!name || !tag) {
      this.searchError.set('Please enter both a player name and tag (e.g. PlayerName#EUW)');
      return;
    }
    this.searchError.set('');
    this.router.navigate(['/player', name, tag]);
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
