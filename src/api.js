export const API = import.meta.env.VITE_API_URL || import.meta.env.VITE_SIM_API || '';
export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API}${path}`, { credentials: 'include', ...options, headers: { ...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), ...options.headers } });
  } catch(error) {
    if(error.name==='AbortError')throw error;
    throw new Error('No se pudo conectar con el servidor. Verifica que esté iniciado y vuelve a intentar.',{cause:error});
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if(response.status===401&&path!=='/api/auth/login')window.dispatchEvent(new Event('metaride:unauthorized'));
    if(response.status===502||response.status===503||response.status===504)throw new Error('El servidor no está disponible. Inicia el backend y vuelve a intentar.');
    throw new Error(typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map(x => `${x.loc.at(-1)}: ${x.msg}`).join('; ') : body.detail?.message ? `${body.detail.message}. ${(body.detail.errors||[]).map(e=>`Fila ${e.row}: ${e.error}`).join('; ')}` : `Error ${response.status}`);
  }
  return response.json();
}
export const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });
