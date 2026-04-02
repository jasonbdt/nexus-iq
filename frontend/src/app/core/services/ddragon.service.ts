import { Injectable } from '@angular/core';

const CDN_BASE = '/api/v1/cdn';
const DDragon_BASE = `${CDN_BASE}/16.7.1/img`;

/**
 * Provides URLs for DDragon static assets served through the backend.
 * Path structure matches Riot's CDN (no /ddragon prefix).
 */
@Injectable({ providedIn: 'root' })
export class DdragonService {
  profileIconUrl(iconId: number): string {
    return `${DDragon_BASE}/profileicon/${iconId}.webp`;
  }

  championImageUrl(championName: string): string {
    return `${DDragon_BASE}/champion/${championName}.webp`;
  }

  itemImageUrl(itemId: number): string {
    return `${DDragon_BASE}/item/${itemId}.webp`;
  }

  spellImageUrl(spellName: string): string {
    return `${DDragon_BASE}/spell/${spellName}.webp`;
  }

  runeStyleImageUrl(runeStyle: string): string {
    runeStyle = runeStyle.replaceAll('.png', '.webp')
    return `${CDN_BASE}/img/${runeStyle}`;
  }

  laneImageUrl(laneName: string): string {
    return `${CDN_BASE}/img/lane-images/${laneName}.webp`;
  }

  /** Rank wings border by tier. Uses wings_{tier}_plate.png (profile icon border). Place in cdn/VERSION/img/ranked-emblem/wings/ */
  rankWingsUrl(tier: string): string {
    const t = tier?.toLowerCase() ?? 'unranked';
    return `${DDragon_BASE}/ranked-emblem/wings/wings_${t}_plate.webp`;
  }
}
