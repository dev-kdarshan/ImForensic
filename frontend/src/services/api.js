const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request(path, options = {}) {
  let response;
  try { response = await fetch(API_BASE + path, options); }
  catch { throw new Error('Cannot reach the ImForensic API gateway. Confirm that Docker services are running and VITE_API_BASE_URL is correct.'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || body.message || ('Request failed (' + response.status + ')');
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return body;
}
export const getHealth = () => request('/health');
export function createAnalysis(file) {
  const data = new FormData();
  data.append('file', file, file.name);
  return request('/api/v1/analyses', { method: 'POST', body: data });
}
export const getAnalysis = (id) => request('/api/v1/analyses/' + encodeURIComponent(id));
