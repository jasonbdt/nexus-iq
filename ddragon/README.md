# DDragon Static Assets

Place Data Dragon (DDragon) files here to serve them through the backend. The directory structure must match Riot's CDN paths.

## Required structure

```
ddragon/
  cdn/
    16.4.1/
      img/
        profileicon/      ← Profile icons (1.png, 29.png, etc.)
        champion/         ← Champion images (Jinx.png, etc.)
        ranked-emblem/
          wings/          ← Rank wings (wings_iron.png, wings_gold.png, etc.)
```

## Download from DDragon / Community Dragon

- **Profile icons**: https://ddragon.leagueoflegends.com/cdn/16.4.1/img/profileicon/
- **Champions**: https://ddragon.leagueoflegends.com/cdn/16.4.1/img/champion/
- **Rank wings (borders)**: https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/ranked-emblem/wings/ (wings_iron_plate.png, wings_gold_plate.png, etc.)

After adding files, the app will serve them at `/api/v1/cdn/16.4.1/img/...` (no `/ddragon` prefix).
