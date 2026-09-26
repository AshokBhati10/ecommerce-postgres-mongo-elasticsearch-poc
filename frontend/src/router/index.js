import { createRouter, createWebHistory } from 'vue-router'
import Storefront from '../views/Storefront.vue'
import Checkout from '../views/Checkout.vue'
import AdminSearch from '../views/AdminSearch.vue'
import OrderDetails from '../views/OrderDetails.vue'
import CatalogAdmin from '../views/CatalogAdmin.vue'

const routes = [
  { path: '/', name: 'storefront', component: Storefront },
  { path: '/checkout', name: 'checkout', component: Checkout },
  { path: '/admin', name: 'admin', component: AdminSearch },
  { path: '/admin/orders/:id', name: 'order-details', component: OrderDetails, props: true },
  { path: '/admin/catalog', name: 'catalog', component: CatalogAdmin }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
