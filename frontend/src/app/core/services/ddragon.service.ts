import { Injectable } from '@angular/core';

const DDragon_BASE = '/api/v1/cdn/16.4.1/img';

/**
 * Provides URLs for DDragon static assets served through the backend.
 * Path structure matches Riot's CDN (no /ddragon prefix).
 */
@Injectable({ providedIn: 'root' })
export class DdragonService {
  profileIconUrl(iconId: number): string {
    return `${DDragon_BASE}/profileicon/${iconId}.png`;
  }

  championImageUrl(championName: string): string {
    return `${DDragon_BASE}/champion/${championName}.png`;
  }

  itemImageUrl(itemId: number): string {
    return `${DDragon_BASE}/item/${itemId}.png`;
  }

  /** Rank wings border by tier. Uses wings_{tier}_plate.png (profile icon border). Place in cdn/VERSION/img/ranked-emblem/wings/ */
  rankWingsUrl(tier: string): string {
    const t = tier?.toLowerCase() ?? 'unranked';
    return `${DDragon_BASE}/ranked-emblem/wings/wings_${t}_plate.png`;
  }
}
