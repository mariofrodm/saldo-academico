import {test, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {api, startSession, sessionEvents, ApiError} from '../src/session.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; startSession(); });
const response = (status, data) => ({ok: status < 400, status, json: async () => data});

test('recupera el CSRF rotado por Swagger y reenvía una sola vez para la misma cuenta', async () => {
  startSession();
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url, ...options});
    if (calls.length === 1) return response(200, {id: 4, csrf: 'initial'});
    if (calls.length === 2) return response(403, {detail: 'Falta protección CSRF'});
    if (calls.length === 3) return response(200, {id: 4, csrf: 'rotated'});
    return response(200, {response: 'Resultado comprobado', conversation_id: 'same-chat'});
  };
  await api('/me');
  const result = await api('/ai/goals', 'POST', {prompt: 'Compara mis aportes', conversation_id: 'same-chat'});
  assert.equal(result.response, 'Resultado comprobado');
  assert.deepEqual(calls.map(c => [c.url, c.method]), [
    ['/api/v1/me', 'GET'], ['/api/v1/ai/goals', 'POST'], ['/api/v1/me', 'GET'], ['/api/v1/ai/goals', 'POST'],
  ]);
  assert.equal(calls[1].headers['X-CSRF-Token'], 'initial');
  assert.equal(calls[3].headers['X-CSRF-Token'], 'rotated');
  assert.equal(calls[1].body, calls[3].body);
  assert.ok(calls.every(c => c.credentials === 'same-origin'));
});

test('un cambio a otra identidad impide reenviar la consulta y pide iniciar sesión', async () => {
  startSession('old', 4);
  let calls = 0, expired = 0;
  const listener = () => { expired += 1; };
  sessionEvents.addEventListener('expired', listener);
  try {
    globalThis.fetch = async () => ++calls === 1
      ? response(403, {detail: 'Falta protección CSRF'})
      : response(200, {id: 1, csrf: 'another-account'});
    await assert.rejects(api('/ai/goals', 'POST', {prompt: 'Mi fondo'}), e => e instanceof ApiError && e.status === 401);
    assert.equal(calls, 2);
    assert.equal(expired, 1);
  } finally { sessionEvents.removeEventListener('expired', listener); }
});

test('sin identidad conocida no reintenta mutaciones', async () => {
  startSession('unknown');
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return response(403, {detail: 'Falta protección CSRF'}); };
  await assert.rejects(api('/goals', 'POST', {name: 'Mi fondo'}), e => e.status === 401);
  assert.equal(calls, 1);
});

test('un segundo rechazo CSRF se muestra con instrucciones y no produce un bucle', async () => {
  startSession('old', 4);
  let calls = 0;
  globalThis.fetch = async () => ++calls === 2
    ? response(200, {id: 4, csrf: 'new'})
    : response(403, {detail: 'Falta protección CSRF'});
  await assert.rejects(api('/ai/goals', 'POST', {prompt: 'Mi fondo'}), /Recarga la página/);
  assert.equal(calls, 3);
});

test('los permisos denegados y los límites IA no se reintentan automáticamente', async () => {
  for (const [status, detail] of [[403, 'Solo administración'], [429, 'Cuota agotada'], [502, 'Proveedor no disponible']]) {
    startSession('valid', 4);
    let calls = 0;
    globalThis.fetch = async () => { calls += 1; return response(status, {detail}); };
    await assert.rejects(api('/ai/goals', 'POST', {prompt: 'Mi fondo'}), e => e.status === status);
    assert.equal(calls, 1);
  }
});

test('una comprobación de CSRF tardía no reenvía datos ni cierra la cuenta nueva', async () => {
  startSession('old', 4);
  let finish, ready, expired = 0, calls = 0;
  const waiting = new Promise(resolve => { ready = resolve; });
  const listener = () => { expired += 1; };
  sessionEvents.addEventListener('expired', listener);
  try {
    globalThis.fetch = () => {
      calls += 1;
      if (calls === 1) return Promise.resolve(response(403, {detail: 'Falta protección CSRF'}));
      return new Promise(resolve => { finish = resolve; ready(); });
    };
    const pending = api('/ai/goals', 'POST', {prompt: 'Mi fondo'});
    await waiting;
    startSession('new-account', 2);
    finish(response(200, {id: 4, csrf: 'old-account-refresh'}));
    await assert.rejects(pending, /sesión ha cambiado/);
    assert.equal(calls, 2);
    assert.equal(expired, 0);
  } finally { sessionEvents.removeEventListener('expired', listener); }
});

test('la comprobación de sesión caducada impide el reenvío', async () => {
  startSession('old', 4);
  let calls = 0;
  globalThis.fetch = async () => ++calls === 1
    ? response(403, {detail: 'Falta protección CSRF'})
    : response(401, {detail: 'Sesión caducada'});
  await assert.rejects(api('/ai/goals', 'POST', {prompt: 'Mi fondo'}), e => e.status === 401);
  assert.equal(calls, 2);
});

test('un GET me de otra cuenta no actualiza el espacio de la cuenta anterior', async () => {
  startSession('initial', 4);
  globalThis.fetch = async () => response(200, {id: 1, csrf: 'another-account'});
  await assert.rejects(api('/me'), /cambió de usuario/);
});
