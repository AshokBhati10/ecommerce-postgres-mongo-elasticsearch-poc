import { reactive, computed, watch } from 'vue'

// Tiny shared store (no extra deps): logged-in user + cart, persisted in localStorage.

function loadJson(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const store = reactive({
  user: loadUser(),
  // productId -> { product: { id, title, price }, quantity }
  cart: loadJson('shop.cart') || {}
})

// Every user in the store must carry a known role. The role can be missing
// (older backend not returning it, stale localStorage) or unexpected —
// either case used to make the router guard redirect / to / forever,
// aborting the post-login navigation until a manual refresh.
function normalizeRole(u) {
  if (u) {
    const r = String(u.role || '').toLowerCase()
    u.role = r === 'admin' ? 'admin' : 'customer'
  }
  return u
}

function loadUser() {
  return normalizeRole(loadJson('shop.user'))
}

export function setUser(user) {
  store.user = normalizeRole(user)
}

export function logout() {
  store.user = null
}

// Role of the selected (simulated-login) user: 'admin' or 'customer'.
export const userRole = computed(() => store.user?.role || null)

export const isAdmin = computed(() => userRole.value === 'admin')

export const isCustomer = computed(() => userRole.value === 'customer')

export function roleLabel(role) {
  return role === 'admin' ? 'Admin' : 'Customer'
}

export function addToCart(product, qty = 1) {
  const id = String(product.id)
  const entry = store.cart[id] || {
    product: { id: product.id, title: product.title, price: product.price },
    quantity: 0
  }
  entry.quantity += qty
  store.cart[id] = entry
}

export function removeFromCart(id) {
  delete store.cart[String(id)]
}

export function setQuantity(id, qty) {
  const key = String(id)
  if (!store.cart[key]) return
  if (qty <= 0) removeFromCart(key)
  else store.cart[key].quantity = qty
}

export function clearCart() {
  store.cart = {}
}

export const cartCount = computed(() =>
  Object.values(store.cart).reduce((n, e) => n + (e.quantity || 0), 0)
)

export const cartTotal = computed(() =>
  Object.values(store.cart).reduce((n, e) => n + (e.quantity || 0) * (e.product.price || 0), 0)
)

export function formatPrice(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v ?? '')
  return '$' + n.toFixed(2)
}

export function fmtDate(s) {
  if (!s) return ''
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString()
}

watch(
  () => store.user,
  (u) => {
    if (u) localStorage.setItem('shop.user', JSON.stringify(u))
    else localStorage.removeItem('shop.user')
  },
  { deep: true }
)

watch(
  () => store.cart,
  (c) => localStorage.setItem('shop.cart', JSON.stringify(c)),
  { deep: true }
)
