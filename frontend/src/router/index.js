import { createRouter, createWebHistory } from 'vue-router'
import { store } from '../store.js'
import Storefront from '../views/Storefront.vue'
import Checkout from '../views/Checkout.vue'
import AdminSearch from '../views/AdminSearch.vue'
import OrderDetails from '../views/OrderDetails.vue'
import CatalogAdmin from '../views/CatalogAdmin.vue'
import Login from '../views/Login.vue'
import MyOrders from '../views/MyOrders.vue'

// Role-based access for this POC's simulated login.
// 'customer': Storefront, Checkout, My Orders
// 'admin':    Storefront, Admin Search, Catalog
const routes = [
  { path: '/login', name: 'login', component: Login },
  { path: '/', name: 'storefront', component: Storefront,
    meta: { requiresAuth: true, roles: ['customer', 'admin'] } },
  { path: '/checkout', name: 'checkout', component: Checkout,
    meta: { requiresAuth: true, roles: ['customer'] } },
  { path: '/orders', name: 'my-orders', component: MyOrders,
    meta: { requiresAuth: true, roles: ['customer'] } },
  { path: '/admin', name: 'admin', component: AdminSearch,
    meta: { requiresAuth: true, roles: ['admin'] } },
  { path: '/admin/orders/:id', name: 'order-details', component: OrderDetails, props: true,
    meta: { requiresAuth: true, roles: ['admin'] } },
  { path: '/admin/catalog', name: 'catalog', component: CatalogAdmin,
    meta: { requiresAuth: true, roles: ['admin'] } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const user = store.user

  // Login page: already signed in → go shopping.
  if (to.name === 'login') {
    return user ? { name: 'storefront' } : true
  }

  // Everything else needs a selected account first.
  if (!user) return { name: 'login' }

  // Role check: wrong role → back to the storefront.
  // The role is normalized defensively: setUser/loadUser guarantee a known
  // value, but an unknown one must never cause a redirect loop (/ -> /),
  // which aborts navigation and strands the user on the login page.
  const role = user.role === 'admin' ? 'admin' : 'customer'
  const roles = to.meta.roles
  if (roles && !roles.includes(role)) {
    return { name: 'storefront' }
  }
  return true
})

export default router
