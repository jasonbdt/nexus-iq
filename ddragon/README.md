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

## Docker and production

- **Local Compose (with `compose.override.yaml`)**: the repo’s `ddragon/` tree is bind-mounted at `/usr/src/ddragon` so the `cdn/` directory stays writable on every host (including Windows). The image does not embed the CDN.
- **Production**: use `docker compose -f compose.yaml -f compose.prod.yaml up` (do not merge the dev override). A named volume is mounted at `/usr/src/ddragon/cdn`, and the backend downloads the Riot `dragontail` archive on first start when `DDRAGON_SYNC_ON_START=true`. Set `DDRAGON_PATCH_VERSION` to the same patch as the frontend (e.g. `16.7.1` in `DdragonService`); if unset, the app uses the latest version from Riot’s API and you should align the frontend URLs to that patch.
