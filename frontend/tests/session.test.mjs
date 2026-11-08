import {test, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {api, startSession, sessionEvents, ApiError} from '../src/session.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; startSession(); });
const response = (status, data) => ({ok: status < 400, status, json: async () => data});

test('descarta datos de la cuenta anterior y usa el CSRF de la cuenta nueva', async () => {
  startSession('admin-csrf');
  let complete;
  globalThis.fetch = () => new Promise(resolve => { complete = resolve; });
  const pending = api('/admin/users');
  startSession('ana-csrf');
  complete(response(200, [{email: 'admin@example.test'}]));
  await assert.rejects(pending, /sesión ha cambiado/);
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.headers['X-CSRF-Token'], 'ana-csrf');
    return response(200, {id: 2});
  };
  assert.deepEqual(await api('/me'), {id: 2});
});

test('un 401 tardío de la cuenta anterior no cierra la sesión nueva', async () => {
  startSession('old');
  let complete, expired = 0;
  const listener = () => { expired += 1; };
  sessionEvents.addEventListener('expired', listener);
  try {
    globalThis.fetch = () => new Promise(resolve => { complete = resolve; });
    const pending = api('/me');
    startSession('new');
    complete(response(401, {detail: 'Sesión inválida'}));
    await assert.rejects(pending, /sesión ha cambiado/);
    assert.equal(expired, 0);
  } finally { sessionEvents.removeEventListener('expired', listener); }
});

test('un 401 de la sesión actual avisa al login y limpia su CSRF', async () => {
  startSession('expired-csrf');
  let expired = 0;
  const listener = () => { expired += 1; };
  sessionEvents.addEventListener('expired', listener);
  try {
    globalThis.fetch = async () => response(401, {detail: 'Sesión caducada'});
    await assert.rejects(api('/board'), /Sesión caducada/);
    assert.equal(expired, 1);
    globalThis.fetch = async (_url, options) => {
      assert.equal(options.headers['X-CSRF-Token'], '');
      return response(200, {});
    };
    await api('/me');
  } finally { sessionEvents.removeEventListener('expired', listener); }
});

test('un intento de login fallido conserva el formulario y su error', async () => {
  let expired = 0;
  const listener = () => { expired += 1; };
  sessionEvents.addEventListener('expired', listener);
  try {
    globalThis.fetch = async () => response(401, {detail: 'Credenciales incorrectas'});
    await assert.rejects(api('/auth/login', 'POST', {}), /Credenciales incorrectas/);
    assert.equal(expired, 0);
  } finally { sessionEvents.removeEventListener('expired', listener); }
});

test('el bloqueo conserva mensaje, conversación y espera para el reintento del chat', async () => {
  globalThis.fetch = async () => ({...response(429, {detail: 'Espera un momento', conversation_id: 'own-chat', request_id: 'request-1', retry_after: 31}), headers: new Headers({'Retry-After': '32'})});
  await assert.rejects(api('/ai/rag', 'POST', {prompt: '¿Y ese mes?'}), error => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, 'Espera un momento');
    assert.equal(error.status, 429);
    assert.equal(error.retryAfter, 32);
    assert.equal(error.conversationId, 'own-chat');
    assert.equal(error.requestId, 'request-1');
    return true;
  });
});


test('el bloqueo informa modo de datos locales sin perder la conversación', async () => {
  globalThis.fetch = async () => ({...response(429, {detail: 'La IA continúa a las 18:00. Puedes consultar cifras.', limit_kind: 'day', local_available: true, conversation_id: 'chat-local', request_id: 'limite-1'}), headers: new Headers({'Retry-After': '300'})});
  await assert.rejects(api('/ai/budget', 'POST', {prompt: 'Revisa octubre'}), error => {
    assert.equal(error.limitKind, 'day');
    assert.equal(error.localAvailable, true);
    assert.equal(error.conversationId, 'chat-local');
    assert.equal(error.retryAfter, 300);
    assert.match(error.message, /18:00/);
    return true;
  });
  globalThis.fetch = async (_url, options) => {
    assert.equal(JSON.parse(options.body).local_only, true);
    return response(200, {response:'En octubre el margen registrado fue Q73.', conversation_id:'chat-local'});
  };
  assert.match((await api('/ai/budget', 'POST', {prompt:'¿Cuánto margen dejó octubre?', conversation_id:'chat-local', local_only:true})).response, /Q73/);
});
