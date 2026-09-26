<template>
  <div class="container">
    <h1 class="page-title">Storefront</h1>

    <div class="card">
      <div class="filters-row">
        <div class="field">
          <label>Log In As</label>
          <select class="select" :value="store.user ? String(store.user.id) : ''" @change="onUserChange">
            <option value="">— Guest —</option>
            <option v-for="u in users" :key="u.id" :value="String(u.id)">
              {{ u.name }} ({{ u.email }})
            </option>
          </select>
        </div>
        <div class="field">
          <label>Category</label>
          <select class="select" v-model="category" @change="loadProducts">
            <option value="">All categories</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label>Search</label>
          <input class="input" v-model="q" @input="onSearchInput" placeholder="Search products…" />
        </div>
      </div>
      <div v-if="!store.user" class="note">
        Pick a user above to enable checkout — placing an order requires a user_id.
      </div>
    </div>

    <div v-if="loading" class="loading">Loading products…</div>
    <div v-else-if="error" class="alert alert-error">{{ error }}</div>
    <div v-else-if="products.length === 0" class="empty card">No products found.</div>
    <div v-else class="grid">
      <div v-for="p in products" :key="p.id" class="card product-card">
        <h3>{{ p.title }}</h3>
        <div class="desc">{{ shortDesc(p.description) }}</div>
        <div class="attr-line" v-if="p.attributes && p.attributes.brand">
          <b>Brand:</b> {{ p.attributes.brand }}
        </div>
        <div class="attr-line" v-if="p.attributes && p.attributes.color">
          <b>Color:</b> {{ p.attributes.color }}
        </div>
        <div class="attr-line" v-if="p.tags && p.tags.length">
          <b>Tags:</b> {{ p.tags.join(', ') }}
        </div>
        <div class="price">{{ formatPrice(p.price) }}</div>
        <button class="btn btn-primary" @click="addToCart(p)">Add to Cart</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'
import { store, setUser, addToCart, formatPrice } from '../store.js'

const users = ref([])
const categories = ref([])
const products = ref([])
const category = ref('')
const q = ref('')
const loading = ref(false)
const error = ref('')
let searchTimer = null

function onUserChange(e) {
  const id = e.target.value
  const user = users.value.find((u) => String(u.id) === id) || null
  setUser(user)
}

function shortDesc(d) {
  if (!d) return ''
  return d.length > 120 ? d.slice(0, 120) + '…' : d
}

async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    products.value = await api.listProducts({ category: category.value, q: q.value })
  } catch (e) {
    error.value = 'Could not load products: ' + e.message
  } finally {
    loading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadProducts, 350)
}

onMounted(async () => {
  try {
    users.value = await api.listUsers()
  } catch (e) {
    error.value = 'Could not load users: ' + e.message
  }
  try {
    categories.value = await api.listCategories()
  } catch {
    // categories are optional — storefront works without them
  }
  await loadProducts()
})
</script>
