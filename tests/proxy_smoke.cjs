// Check the unchanged production SSR proxy against tests.proxy_app.
const assert = require('node:assert/strict');

async function run() {
  const base = process.env.NEXUS_TEST_PROXY_URL || 'http://localhost:4301/api/v1';
  const json = async (path, options) => {
    const response = await fetch(base + path, options);
    assert(response.ok, `${path}: ${response.status}`);
    return response.json();
  };
  assert.equal((await json('/')).status, 200);
  const player = await json('/search/EUW/Test%20Player');
  assert.deepEqual(player.leagues, []);
  const registered = await json('/register', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({emailAddress: 'new@test.example', password: 'password',
      password_confirm: 'password', gameName: 'Test Player', tagLine: 'EUW'}),
  });
  assert.equal(registered.linked_summoner.puuid, 'p'.repeat(78));
  const login = await json('/login', {method: 'POST',
    body: new URLSearchParams({username: 'active@example.test', password: 'password'})});
  const headers = {Authorization: `Bearer ${login.access_token}`};
  const profile = await json('/users/me', {headers});
  assert.equal(profile.emailAddress, 'active@example.test');
  const matches = await json('/matches/euw/by-puuid/' + 'p'.repeat(78));
  assert.equal(matches[0].teams[0].participants[0].spell_1, 'SummonerFlash');
  assert.deepEqual(await json('/update/' + 'p'.repeat(78), {method: 'PATCH', headers}),
    {message: 'Update queued'});
  const session = await json('/coach/sessions', {method: 'POST',
    headers: {...headers, 'Content-Type': 'application/json'}, body: '{}'});
  const streamed = await fetch(base + `/coach/sessions/${session.id}/chat?question=Question`,
    {method: 'POST', headers});
  assert.equal(streamed.status, 200);
  const stream = await streamed.text();
  assert(stream.includes('"delta": "Hello"'));
  assert(stream.endsWith('data: [DONE]\n\n'));
  const saved = await json(`/coach/sessions/${session.id}`, {headers});
  assert.equal(saved.messages[1].content, 'Hello world');
  const stateless = await fetch(base + '/query/stream?question=Question', {method: 'POST'});
  assert((await stateless.text()).endsWith('data: [DONE]\n\n'));
  console.log('Proxy smoke passed: search, registration, login, profile, matches, queue, coaching and RAG streams.');
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
