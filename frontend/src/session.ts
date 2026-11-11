let csrf = '';
let generation = 0;
let sessionUserId: number | null = null;

export const sessionEvents = new EventTarget();

export function startSession(token = '', userId: number | null = null) {
  generation += 1;
  csrf = token;
  sessionUserId = userId;
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
  const requestUserId = sessionUserId;
  const serializedBody = body === undefined ? undefined : JSON.stringify(body);
  const send = () => fetch('/api/v1' + path, {
    method,
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
    body: serializedBody,
  });
  let response = await send();
  let data = await response.json();
  // A response from a previous account must never update the current workspace.
  if (requestGeneration !== generation) throw new Error('La sesión ha cambiado.');
  const expire = () => {
    startSession();
    sessionEvents.dispatchEvent(new Event('expired'));
  };
  const csrfRejected = () => response.status === 403 && data.detail === 'Falta protección CSRF';
  // A login in Swagger or another tab can rotate the shared cookie. The rejected
  // request has not reached its handler, so it is safe to retry exactly once,
  // after confirming that the cookie still belongs to the displayed account.
  if (csrfRejected() && !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())
      && !['/auth/login', '/auth/register'].includes(path)) {
    if (requestUserId === null) {
      expire();
      throw new ApiError(401, {detail: 'Inicia sesión de nuevo para continuar con tu cuenta.'});
    }
    const current = await fetch('/api/v1/me', {method: 'GET', credentials: 'same-origin', headers: {'Accept': 'application/json'}});
    const identity = await current.json();
    if (requestGeneration !== generation) throw new Error('La sesión ha cambiado.');
    if (!current.ok || !identity || typeof identity !== 'object' || identity.id !== requestUserId || typeof identity.csrf !== 'string' || !identity.csrf) {
      if (current.status === 401 || current.ok) {
        expire();
        throw new ApiError(401, {detail: 'La sesión cambió. Inicia sesión de nuevo para continuar con tu cuenta.'});
      }
      throw new ApiError(current.status, {detail: 'No se pudo comprobar tu sesión. Vuelve a intentarlo.'});
    }
    csrf = identity.csrf;
    response = await send();
    data = await response.json();
    if (requestGeneration !== generation) throw new Error('La sesión ha cambiado.');
    if (csrfRejected()) {
      throw new ApiError(403, {detail: 'Tu sesión volvió a cambiar. Recarga la página y vuelve a intentarlo.'});
    }
  }
  if (!response.ok) {
    if (response.status === 401 && !['/auth/login', '/auth/register'].includes(path)) {
      expire();
    }
    throw new ApiError(response.status, data, response.headers?.get('Retry-After'));
  }
  if (path === '/me' && method.toUpperCase() === 'GET' && Number.isSafeInteger(data.id) && typeof data.csrf === 'string') {
    if (sessionUserId !== null && sessionUserId !== data.id) {
      expire();
      throw new ApiError(401, {detail: 'La sesión cambió de usuario. Inicia sesión de nuevo.'});
    }
    sessionUserId = data.id;
    csrf = data.csrf;
  }
  return data;
}
