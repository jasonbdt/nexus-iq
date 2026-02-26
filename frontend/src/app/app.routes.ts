import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
    canActivate: [authGuard],
  },
  {
    path: 'player/:gameName/:tagLine',
    loadComponent: () =>
      import('./features/player-details/player-details.component').then(
        (m) => m.PlayerDetailsComponent,
      ),
  },
  {
    path: 'coach',
    loadComponent: () =>
      import('./features/coach/coach.component').then((m) => m.CoachComponent),
    canActivate: [authGuard],
  },
  {
    path: 'admin',
    loadComponent: () =>
      import('./features/admin/admin.component').then((m) => m.AdminComponent),
    canActivate: [authGuard, adminGuard],
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/settings.component').then((m) => m.SettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: '**',
    redirectTo: '',
  },
];
