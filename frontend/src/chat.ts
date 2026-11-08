export type ChatFailure = {
  message: string;
  status?: number;
  requestId?: string;
  retryAt: number;
};

export type ChatTurn = {
  id: string;
  prompt: string;
  status: 'pending' | 'success' | 'failed';
  response?: string;
  failure?: ChatFailure;
};

export type ChatState = {
  conversationId: string | null;
  draft: string;
  turns: ChatTurn[];
};

export const emptyChat = (): ChatState => ({conversationId: null, draft: '', turns: []});

export function beginQuestion(chat: ChatState, text: string, id: string, retryId?: string) {
  const prompt = text.trim();
  if (prompt.length < 3 || prompt.length > 1000 || chat.turns.some(turn => turn.status === 'pending')) {
    throw new Error('La pregunta no puede enviarse todavía.');
  }
  const latest = chat.turns.at(-1);
  // Re-sending the same failed question is a retry, including from the composer.
  const reused = latest?.status === 'failed' &&
    (retryId === latest.id || (!retryId && latest.prompt === prompt));
  if (retryId && !reused) throw new Error('Solo se puede reintentar la última pregunta pendiente de respuesta.');
  const turnId = reused ? latest.id : id;
  const turn: ChatTurn = {id: turnId, prompt: reused ? latest.prompt : prompt, status: 'pending'};
  return {
    turnId,
    chat: {...chat, draft: retryId ? chat.draft : '',
      turns: reused ? [...chat.turns.slice(0, -1), turn] : [...chat.turns, turn]},
  };
}

export function completeQuestion(chat: ChatState, id: string, response: string, conversationId: string): ChatState {
  return {...chat, conversationId,
    turns: chat.turns.map(turn => turn.id === id ? {...turn, status: 'success', response, failure: undefined} : turn)};
}

export function failQuestion(chat: ChatState, id: string, error: unknown, now = Date.now()): ChatState {
  const details = error && typeof error === 'object' ? error as Record<string, unknown> : {};
  const delay = typeof details.retryAfter === 'number' && Number.isFinite(details.retryAfter)
    ? Math.max(0, Math.ceil(details.retryAfter)) : 0;
  let message = typeof details.message === 'string' && details.message
    ? details.message : 'No pude completar la respuesta. Puedes volver a intentarlo.';
  if (error instanceof TypeError && /fetch|network|load failed/i.test(message)) {
    message = 'No se pudo conectar. Comprueba tu conexión y vuelve a intentarlo.';
  }
  const failure: ChatFailure = {
    message,
    status: typeof details.status === 'number' ? details.status : undefined,
    requestId: typeof details.requestId === 'string' ? details.requestId : undefined,
    retryAt: now + delay * 1000,
  };
  return {...chat,
    conversationId: typeof details.conversationId === 'string' && details.conversationId
      ? details.conversationId : chat.conversationId,
    turns: chat.turns.map(turn => turn.id === id ? {...turn, status: 'failed', failure} : turn),
  };
}

export function retrySeconds(retryAt: number, now = Date.now()) {
  return Math.max(0, Math.ceil((retryAt - now) / 1000));
}

export function waitLabel(seconds: number) {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
  return `${Math.ceil(seconds / 3600)} h`;
}

// Rendering uses React text nodes only. Historical content and numeric symbols
// remain untouched; this only separates paragraphs and normalizes line endings.
export function proseParagraphs(text: string) {
  return text.replace(/\r\n?/g, '\n').split(/\n\s*\n/).map(part => part.trim()).filter(Boolean);
}
