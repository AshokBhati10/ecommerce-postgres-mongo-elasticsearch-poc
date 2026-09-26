<template>
  <div class="container">
    <h1 class="page-title">Admin · Order Search</h1>

    <div class="kpis">
      <div class="kpi">
        <div class="label">Total revenue</div>
        <div class="value">{{ formatPrice(aggs.total_revenue || 0) }}</div>
      </div>
      <div class="kpi" v-for="s in statusCounts" :key="s.status">
        <div class="label">{{ statusLabel(s.status) }}</div>
        <div class="value">{{ s.count }}</div>
      </div>
      <div class="kpi">
        <div class="label">Orders found</div>
        <div class="value">{{ total }}</div>
      </div>
    </div>

    <div class="admin-layout">
      <aside class="card">
        <div class="facet-group">
          <div class="facet-title">Status</div>
          <label class="checkbox-line" v-for="s in allStatuses" :key="s.value">
            <input type="checkbox" :value="s.value" v-model="statuses" @change="search" />
            {{ s.label }}
          </label>
        </div>
        <div class="facet-group">
          <div class="facet-title">Order date</div>
          <div class="field"><label>From</label><input type="date" class="input" v-model="dateFrom" @change="search" /></div>
          <div class="field"><label>To</label><input type="date" class="input" v-model="dateTo" @change="search" /></div>
        </div>
        <div class="facet-group">
          <div class="facet-title">Total amount</div>
          <div class="field"><label>Min</label><input type="number" min="0" step="0.01" class="input" v-model.number="minTotal" @change="search" /></div>
          <div class="field"><label>Max</label><input type="number" min="0" step="0.01" class="input" v-model.number="maxTotal" @change="search" /></div>
        </div>
      </aside>

      <div>
        <div class="card">
          <input
            class="input"
            v-model="q"
            @input="onQ"
            placeholder="Omni-search: order id, customer, product title…"
          />
          <div class="note" style="margin-top: 0.4rem">
            Powered by Elasticsearch only — no PostgreSQL/MongoDB reads here.
          </div>
        </div>

        <div v-if="loading" class="loading">Searching…</div>
        <div v-else-if="error" class="alert alert-error">{{ error }}</div>
        <div v-else-if="hits.length === 0" class="empty card">No orders match.</div>
        <table v-else class="tbl card">
          <thead>
            <tr><th>Order ID</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr v-for="h in hits" :key="h.order_id">
              <td>
                <router-link :to="{ name: 'order-details', params: { id: h.order_id } }">
                  {{ h.order_id }}
                </router-link>
              </td>
              <td>{{ fmtDate(h.order_date) }}</td>
              <td>{{ h.customer && h.customer.name }}</td>
              <td>{{ formatPrice(h.total_amount) }}</td>
              <td><span class="badge" :class="statusClass(h.status)">{{ statusLabel(h.status) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client.js'
import { formatPrice, fmtDate } from '../store.js'

const q = ref('')
const statuses = ref([])
const dateFrom = ref('')
const dateTo = ref('')
const minTotal = ref(null)
const maxTotal = ref(null)
const hits = ref([])
const total = ref(0)
const aggs = ref({})
const loading = ref(false)
const error = ref('')
let timer = null

const allStatuses = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'SHIPPED', label: 'Shipped' }
]

const statusCounts = computed(() => aggs.value.by_status || [])

function statusLabel(s) {
  return { PENDING: 'Pending', PROCESSING: 'Processing', SHIPPED: 'Shipped' }[s] || s
}

function statusClass(s) {
  return { PENDING: 'badge-amber', PROCESSING: 'badge-blue', SHIPPED: 'badge-green' }[s] || 'badge-gray'
}

async function search() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.searchOrders({
      q: q.value,
      statuses: statuses.value,
      date_from: dateFrom.value || null,
      date_to: dateTo.value || null,
      min_total: minTotal.value ?? null,
      max_total: maxTotal.value ?? null,
      size: 50
    })
    hits.value = res.hits || []
    total.value = res.total || 0
    aggs.value = res.aggs || {}
  } catch (e) {
    error.value = 'Search failed: ' + e.message
  } finally {
    loading.value = false
  }
}

function onQ() {
  clearTimeout(timer)
  timer = setTimeout(search, 350)
}

onMounted(search)
</script>
