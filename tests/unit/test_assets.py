"""Asset behavior and public match projections after removing schema filesystem access."""
import json

from PIL import Image

from tests.factories import match


def write_metadata(root):
    base = root / '16.20.1' / 'data' / 'en_US'
    base.mkdir(parents=True)
    (base / 'summoner.json').write_text(json.dumps({'data': {
        'Flash': {'key': '4', 'id': 'SummonerFlash'},
        'Ignite': {'key': '14', 'id': 'SummonerDot'},
    }}), encoding='utf-8')
    (base / 'runesReforged.json').write_text(json.dumps([
        {'id': 8000, 'icon': 'precision.png'}, {'id': 8100, 'icon': 'domination.png'},
    ]), encoding='utf-8')


def test_match_contract_enrichment_and_recent_lane_order(client, services):
    write_metadata(services.assets.root)
    with services.players.uow() as work:
        work.matches.save(match())
        work.commit()
    response = client.get('/matches/euw/by-id/EUW1_123')
    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        'match_id', 'platform', 'queue_id', 'game_mode', 'game_type', 'game_version', 'map_id',
        'game_start', 'game_end', 'game_duration', 'teams',
    }
    player = response.json()['teams'][0]['participants'][0]
    assert player['riot_id'] == 'Player#EUW'
    assert player['spell_1'] == 'SummonerFlash'
    assert player['spell_2'] == 'SummonerDot'
    assert player['primary_style'] == 'precision.png'
    assert player['secondary_style'] == 'domination.png'
    assert (player['kda'], player['total_cs']) == (3.75, 195)
    assert not {'id', 'runes', 'summoner_spell_1', 'summoner_spell_2'} & player.keys()
    recent = client.get('/matches/euw/by-puuid/' + 'p' * 78 + '?match_count=1')
    assert recent.status_code == 200
    assert [entry['lane'] for entry in recent.json()[0]['teams'][0]['participants']] == [
        'TOP', 'UTILITY',
    ]
    assert client.get('/matches/euw/by-id/missing').json() == {'detail': 'Match not found'}


def test_cdn_webp_alias_crop_and_cache(client, services):
    path = services.assets.root / '16.20.1' / 'img' / 'champion' / 'Fiddlesticks.png'
    path.parent.mkdir(parents=True)
    image = Image.new('RGB', (100, 100), 'red')
    for x in range(6, 94):
        for y in range(6, 94):
            image.putpixel((x, y), (0, 0, 255))
    image.save(path)
    url = '/cdn/16.20.1/img/champion/fiddlesticks_cropped.webp'
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/webp'
    cached = path.with_name('fiddlesticks_cropped.webp')
    with Image.open(cached) as converted:
        assert converted.size == (100, 100)
        assert converted.getpixel((0, 0))[2] > 200
    assert client.get(url).content == response.content
    assert client.get('/cdn/16.20.1/img/champion/Fiddlesticks.png').status_code == 404
    assert client.get('/cdn/%2E%2E%2Foutside.webp').status_code == 403


def test_api_schema_serialization_does_not_read_files(client, services, monkeypatch):
    from app.entrypoints.http.schemas import MatchesRead
    write_metadata(services.assets.root)
    projected = services.assets.enrich(match())
    schema = MatchesRead.model_validate(projected)
    def unexpected_read(*_args, **_kwargs):
        raise AssertionError('Serialization attempted a filesystem read')
    monkeypatch.setattr('builtins.open', unexpected_read)
    assert schema.model_dump()['teams'][0]['participants'][0]['spell_1'] == 'SummonerFlash'
