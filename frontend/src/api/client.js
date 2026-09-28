// Fetch wrappers against the FastAPI backend.
// Base URL comes from VITE_API_URL, defaulting to http://localhost:8000.

const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.text()
      if (body) detail = body
    } catch { /* ignore */ }
    throw new Error(`HTTP ${res.status}: ${detail}`)
  }
  if (res.status === 204) return null
  return res.json()
}

const enc = encodeURIComponent

export const api = {
  listUsers: () =>
    request('/api/users'),

  // params: { category?, q?, active?, page?, page_size? } — backend defaults active=true.
  // When `page` is given the backend returns a paginated envelope
  // { items, page, page_size, total, total_pages }; otherwise a plain list.
  listProducts: (params = {}) => {
    const q = new URLSearchParams()
    if (params.category) q.set('category', params.category)
    if (params.q) q.set('q', params.q)
    if (params.active !== undefined) q.set('active', String(params.active))
    if (params.page !== undefined && params.page !== null) q.set('page', String(params.page))
    if (params.page_size !== undefined && params.page_size !== null) q.set('page_size', String(params.page_size))
    const qs = q.toString()
    return request(`/api/products${qs ? `?${qs}` : ''}`)
  },

  listCategories: () =>
    request('/api/products/categories'),

  getProduct: (id) =>
    request(`/api/products/${enc(id)}`),

  createProduct: (data) =>
    request('/api/products', { method: 'POST', body: JSON.stringify(data) }),

  updateProduct: (id, data) =>
    request(`/api/products/${enc(id)}`, { method: 'PUT', body: JSON.stringify(data) }),

  createOrder: (data) =>
    request('/api/orders', { method: 'POST', body: JSON.stringify(data) }),

  getOrder: (id) =>
    request(`/api/orders/${enc(id)}`),

  updateOrderStatus: (id, status) =>
    request(`/api/orders/${enc(id)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    }),

  searchOrders: (filters) =>
    request('/api/search/orders', { method: 'POST', body: JSON.stringify(filters) })
}
