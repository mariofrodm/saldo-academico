import {test} from 'node:test';
import assert from 'node:assert/strict';
import {emptyChat, beginQuestion, completeQuestion, failQuestion, retrySeconds, waitLabel, proseParagraphs} from '../src/chat.ts';

test('un fallo conserva la pregunta y recupera la conversación creada por el servidor', () => {
  const initial = {...emptyChat(), draft: '¿En qué gasté más en octubre?'};
  const pending = beginQuestion(initial, initial.draft, 'turn-1');
  const error = Object.assign(new Error('Espera un momento antes de volver a intentarlo.'), {
    status: 429, retryAfter: 37, conversationId: 'conversation-server', requestId: 'request-server',
  });
  const failed = failQuestion(pending.chat, pending.turnId, error, 1000);
  assert.equal(failed.conversationId, 'conversation-server');
  assert.equal(failed.turns.length, 1);
  assert.equal(failed.turns[0].prompt, initial.draft);
  assert.equal(failed.turns[0].status, 'failed');
  assert.equal(failed.turns[0].failure.message, error.message);
  assert.equal(failed.turns[0].failure.requestId, 'request-server');
  assert.equal(failed.turns[0].failure.retryAt, 38000);
  assert.equal(retrySeconds(failed.turns[0].failure.retryAt, 1001), 37);
  assert.equal(retrySeconds(failed.turns[0].failure.retryAt, 38000), 0);
  assert.equal(initial.turns.length, 0);
});

test('Reintentar sustituye el estado del mismo turno y no duplica la pregunta', () => {
  const original = beginQuestion({...emptyChat(), conversationId: 'october'}, '¿Y en ese mismo mes?', 'turn-1');
  const failed = failQuestion(original.chat, original.turnId, new Error('Espera.'), 1000);
  const retry = beginQuestion({...failed, draft: 'Otra pregunta todavía sin enviar'}, failed.turns[0].prompt, 'unused-id', 'turn-1');
  assert.equal(retry.turnId, 'turn-1');
  assert.equal(retry.chat.turns.length, 1);
  assert.equal(retry.chat.turns[0].status, 'pending');
  assert.equal(retry.chat.turns[0].failure, undefined);
  assert.equal(retry.chat.conversationId, 'october');
  assert.equal(retry.chat.draft, 'Otra pregunta todavía sin enviar');
  const complete = completeQuestion(retry.chat, retry.turnId, 'En octubre gastaste Q1.500 en vivienda.', 'october');
  assert.equal(complete.turns.length, 1);
  assert.equal(complete.turns[0].status, 'success');
  assert.equal(complete.draft, retry.chat.draft);
});

test('reenviar manualmente la última pregunta fallida también evita duplicados', () => {
  const first = beginQuestion(emptyChat(), '¿Cómo organizo mis deudas?', 'first');
  const failed = failQuestion(first.chat, first.turnId, new Error('No disponible.'));
  const retry = beginQuestion(failed, '  ¿Cómo organizo mis deudas?  ', 'second');
  assert.equal(retry.turnId, 'first');
  assert.equal(retry.chat.turns.length, 1);
});

test('una pregunta nueva mantiene el fallo anterior visible y bloquea envíos simultáneos', () => {
  const first = beginQuestion(emptyChat(), '¿Cómo organizo mis deudas?', 'first');
  assert.throws(() => beginQuestion(first.chat, 'Segunda pregunta', 'second'), /todavía/);
  const failed = failQuestion(first.chat, first.turnId, new Error('No disponible.'));
  const second = beginQuestion(failed, '¿Qué metas tengo?', 'second');
  assert.equal(second.chat.turns.length, 2);
  assert.equal(second.chat.turns[0].failure.message, 'No disponible.');
  assert.throws(() => beginQuestion(second.chat, first.chat.turns[0].prompt, 'unused', 'first'));
});

test('no pierde el antecedente de una conversación ante un fallo de red sin ID', () => {
  const question = beginQuestion({...emptyChat(), conversationId: 'known'}, '¿Y en octubre?', 'turn');
  const failed = failQuestion(question.chat, question.turnId, new TypeError('Failed to fetch'), 1000);
  assert.equal(failed.conversationId, 'known');
  assert.match(failed.turns[0].failure.message, /conexión/);
  assert.equal(failed.turns[0].failure.retryAt, 1000);
  for (const retryAfter of [Infinity, NaN, '60', -1]) {
    const noDelay = failQuestion(question.chat, question.turnId, {message: 'Error', retryAfter}, 1000);
    assert.equal(noDelay.turns[0].failure.retryAt, 1000);
  }
});

test('la espera usa tiempo restante real y admite límites mayores de un minuto', () => {
  assert.equal(retrySeconds(61000, 1000), 60);
  assert.equal(waitLabel(59), '59 s');
  assert.equal(waitLabel(60), '1 min');
  assert.equal(waitLabel(3601), '2 h');
  assert.equal(retrySeconds(61000, 70000), 0);
});

test('los párrafos mantienen importes y caracteres como texto, sin reescribir el contenido', () => {
  assert.deepEqual(proseParagraphs('  Ingresaste Q7.250,00.\r\n\r\nTu margen fue Q73,00.\nContinúa revisándolo.  '), [
    'Ingresaste Q7.250,00.', 'Tu margen fue Q73,00.\nContinúa revisándolo.',
  ]);
  assert.deepEqual(proseParagraphs('2 * 3 = 6; reducción -Q25 y ahorro +Q10.\n\n<script>texto</script>'), [
    '2 * 3 = 6; reducción -Q25 y ahorro +Q10.', '<script>texto</script>',
  ]);
  assert.deepEqual(proseParagraphs(' \n\n '), []);
});

test('Nueva conversación crea estado vacío independiente para la cuenta actual', () => {
  const first = beginQuestion(emptyChat(), 'Pregunta de otra conversación', 'first');
  const fresh = emptyChat();
  assert.deepEqual(fresh, {conversationId: null, draft: '', turns: []});
  assert.notEqual(first.chat.turns, fresh.turns);
  assert.equal(first.chat.turns.length, 1);
});
