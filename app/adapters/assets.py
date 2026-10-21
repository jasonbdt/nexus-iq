"""DDragon files, image conversion and explicit match-response enrichment."""
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from PIL import Image
from app.domain.errors import Forbidden, NotFound
from .ddragon_config import ddragon_cdn_root, ddragon_patch_version


def crop_image(img: Image.Image) -> Image.Image:
    """Remove champion-image borders while retaining the original dimensions."""
    width, height = img.size

    crop_x = max(1, round(width * 0.06))
    crop_y = max(1, round(height * 0.06))

    left = crop_x
    top = crop_y
    right = width - crop_x
    bottom = height - crop_y

    if left >= right or top >= bottom:
        raise ValueError("Invalid cropping area")

    cropped = img.crop((left, top, right, bottom))

    return cropped.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )


def convert_png_to_webp(source: Path, target: Path, crop: bool) -> None:
    """Write a converted image through an atomic temporary-file replacement."""
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as img:
        result = crop_image(img) if crop else img.copy()

        if result.mode not in ("RGB", "RGBA"):
            result = result.convert("RGBA")

        with tempfile.NamedTemporaryFile(
            suffix=".webp",
            dir=str(target.parent),
            delete=False
        ) as tmp_file:
            temp_path = Path(tmp_file.name)

        try:
            result.save(temp_path, format="WEBP", quality=90, method=6)
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)


class DDragonAssets:
    """Resolve paths and load data only when requested, outside API schemas."""

    def __init__(self, root: Path | None = None, patch: str | None = None):
        self.root = root
        self.patch = patch

    def file(self, file_path: str) -> Path:
        """Resolve a WebP path, using the original conversion and crop behavior."""
        root = (self.root or ddragon_cdn_root()).resolve()
        if not root.exists():
            raise NotFound('DDragon cache not configured')
        requested = (root / file_path).resolve()
        if not requested.is_relative_to(root):
            raise Forbidden('Invalid path')
        if requested.suffix.lower() != '.webp':
            raise NotFound('File not found')
        if requested.is_file():
            return requested
        stem = requested.stem.removesuffix('_cropped')
        stem = {'fiddlesticks': 'Fiddlesticks'}.get(stem.lower(), stem)
        source = requested.with_name(f'{stem}.png')
        if not source.is_file():
            raise NotFound('Source PNG file not found')
        parts = [part.lower() for part in source.relative_to(root).parts]
        crop = len(parts) >= 4 and parts[1:3] == ['img', 'champion']
        convert_png_to_webp(source, requested, crop)
        return requested

    def enrich(self, match) -> dict:
        """Load each metadata file once, then build a detached public match graph."""
        root = self.root or ddragon_cdn_root()
        patch = self.patch or ddragon_patch_version()
        base = root / patch / 'data' / 'en_US'
        with (base / 'summoner.json').open(encoding='utf-8') as source:
            spells = json.load(source)
        with (base / 'runesReforged.json').open(encoding='utf-8') as source:
            styles = json.load(source)
        spell_ids = {entry['key']: entry.get('id') for entry in spells.get('data', {}).values()}
        style_icons = {entry['id']: entry.get('icon') for entry in styles}
        result = asdict(match)
        for team, entity_team in zip(result['teams'], match.teams):
            for player, entity in zip(team['participants'], entity_team.participants):
                player.update(riot_id=f"{entity.summoner_name}#{entity.tag_line}",
                              kda=entity.kda, total_cs=entity.total_cs,
                              spell_1=spell_ids[str(entity.summoner_spell_1)],
                              spell_2=spell_ids[str(entity.summoner_spell_2)],
                              primary_style=style_icons[entity.runes[0].primary_style],
                              secondary_style=style_icons[entity.runes[0].secondary_style])
        return result
