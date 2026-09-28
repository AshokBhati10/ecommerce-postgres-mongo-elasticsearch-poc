<template>
  <div class="container">
    <h1 class="page-title">My Orders</h1>

    <div v-if="loading" class="loading">Loading your orders…</div>
    <div v-else-if="error" class="alert alert-error">{{ error }}</div>
    <div v-else-if="orders.length === 0" class="empty card">
      You haven't placed any orders yet. <router-link to="/">Browse the storefront</router-link>.
    </div>
    <div v-else>
      <div class="result-meta">Showing {{ orders.length }} most recent orders</div>
      <div v-for="o in orders" :key="o.id" class="card order-card">
        <div class="order-head">
          <div>
            <div class="order-id">Order #{{ o.id }}</div>
            <div class="order-date">{{ fmtDate(o.order_date) }}</div>
          </div>
          <div class="order-side">
            <span class="status-pill" :class="'status-' + o.status.toLowerCase()">{{ o.status }}</span>
            <div class="order-total">{{ formatPrice(o.total_amount) }}</div>
          </div>
        </div>
        <table class="tbl order-items">
          <tbody>
            <tr v-for="it in o.items" :key="it.product_id">
              <td>{{ it.title }}</td>
              <td class="num">× {{ it.quantity }}</td>
              <td class="num">{{ formatPrice(it.unit_price) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'
import { store, formatPrice, fmtDate } from '../store.js'

const orders = ref([])
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  if (!store.user) return
  loading.value = true
  try {
    orders.value = await api.listUserOrders(store.user.id)
  } catch (e) {
    error.value = 'Could not load orders: ' + e.message
  } finally {
    loading.value = false
  }
})
</script>
