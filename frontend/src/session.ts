let csrf = '';
let generation = 0;

export const sessionEvents = new EventTarget();

export function startSession(token = '') {
  generation += 1;
  csrf = token;
}

export function updateCsrf(token: string) {
  csrf = token;
}

export class ApiError extends Error {
  status: number;
  retryAfter: number | null;
  conversationId?: string;
  requestId?: string;
  limitKind?: string;
  localAvailable: boolean;
  constructor(status: number, data: Record<string, unknown>, retryHeader?: string | null) {
    const detail=data.detail && typeof data.detail==='object' && !Array.isArray(data.detail) ? data.detail as Record<string,unknown> : {};
    super(typeof data.detail==='string' ? data.detail : typeof detail.message==='string' ? detail.message : 'Revisa los campos del formulario.');
    this.name = 'ApiError';
    this.status = status;
    const kind=data.limit_kind??detail.limit_kind;
    this.limitKind=typeof kind==='string'?kind:undefined;
    this.localAvailable=(data.local_available??detail.local_available)===true;
    const seconds = Number(retryHeader ?? data.retry_after ?? detail.retry_after);
    this.retryAfter = Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : null;
    this.conversationId = typeof data.conversation_id === 'string' ? data.conversation_id : undefined;
    this.requestId = typeof data.request_id === 'string' ? data.request_id : undefined;
  }
}

export async function api(path: string, method = 'GET', body?: unknown) {
  const requestGeneration = generation;
  const response = await fetch('/api/v1' + path, {
    method,
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  // A response from a previous account must never update the current workspace.
  if (requestGeneration !== generation) throw new Error('La sesión ha cambiado.');
  if (!response.ok) {
    if (response.status === 401 && !['/auth/login', '/auth/register'].includes(path)) {
      startSession();
      sessionEvents.dispatchEvent(new Event('expired'));
    }
    throw new ApiError(response.status, data, response.headers?.get('Retry-After'));
  }
  return data;
}
