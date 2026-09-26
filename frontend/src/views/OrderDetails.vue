<template>
  <div class="container">
    <router-link to="/admin">← Back to search</router-link>
    <h1 class="page-title" style="margin-top: 0.5rem">Order {{ orderId }}</h1>

    <div v-if="loading" class="loading">Loading order…</div>
    <div v-else-if="error" class="alert alert-error">{{ error }}</div>
    <div v-else-if="order">
      <div class="card">
        <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: center">
          <div><b>Date:</b> {{ fmtDate(order.order_date) }}</div>
          <div><b>Customer:</b> {{ order.customer && order.customer.name }} ({{ order.customer && order.customer.email }})</div>
          <div><b>Total:</b> {{ formatPrice(order.total_amount) }}</div>
          <div>
            <span v-if="order.es_in_sync" class="badge badge-green">In sync</span>
            <span v-else class="badge badge-amber">Out of sync</span>
          </div>
        </div>
        <div class="note" style="margin-top: 0.5rem">
          Canonical order details come from PostgreSQL; the badge reflects Elasticsearch sync state.
        </div>
      </div>

      <div class="card">
        <h3>Items</h3>
        <table class="tbl">
          <thead>
            <tr><th>Product</th><th>Qty</th><th>Unit price</th><th>Line total</th></tr>
          </thead>
          <tbody>
            <tr v-for="it in order.items" :key="it.product_id">
              <td>{{ it.title }}</td>
              <td>{{ it.quantity }}</td>
              <td>{{ formatPrice(it.unit_price) }}</td>
              <td>{{ formatPrice(it.unit_price * it.quantity) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h3>Status</h3>
        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap">
          <select class="select" v-model="newStatus" style="max-width: 220px">
            <option value="PENDING">Pending</option>
            <option value="PROCESSING">Processing</option>
            <option value="SHIPPED">Shipped</option>
          </select>
          <button class="btn btn-primary" :disabled="saving || newStatus === order.status" @click="saveStatus">
            {{ saving ? 'Saving…' : 'Update status' }}
          </button>
        </div>
        <div v-if="saveMsg" class="alert" :class="saveOk ? 'alert-success' : 'alert-error'" style="margin-top: 0.75rem">
          {{ saveMsg }}
        </div>
        <div class="note" style="margin-top: 0.5rem">
          Status updates write to PostgreSQL and re-synchronize the order to Elasticsearch.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'
import { formatPrice, fmtDate } from '../store.js'

const props = defineProps({ id: { type: String, required: true } })
const orderId = props.id

const order = ref(null)
const loading = ref(true)
const error = ref('')
const newStatus = ref('')
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(true)

async function load() {
  loading.value = true
  error.value = ''
  try {
    order.value = await api.getOrder(orderId)
    newStatus.value = order.value.status
  } catch (e) {
    error.value = 'Could not load order: ' + e.message
  } finally {
    loading.value = false
  }
}

async function saveStatus() {
  saving.value = true
  saveMsg.value = ''
  try {
    order.value = await api.updateOrderStatus(orderId, newStatus.value)
    saveOk.value = true
    saveMsg.value = 'Status updated.'
  } catch (e) {
    saveOk.value = false
    saveMsg.value = 'Update failed: ' + e.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
