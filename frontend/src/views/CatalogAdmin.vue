<template>
  <div class="container">
    <h1 class="page-title">Admin · Catalog</h1>

    <div class="alert alert-info">
      The catalog lives in MongoDB. Editing a product here never rewrites historical
      orders — orders keep the title/price snapshot taken at checkout.
    </div>

    <div class="card">
      <h3>{{ editingId ? 'Edit product' : 'New product' }}</h3>
      <div v-if="formError" class="alert alert-error">{{ formError }}</div>
      <div v-if="formOk" class="alert alert-success">{{ formOk }}</div>
      <form @submit.prevent="save">
        <div class="filters-row">
          <div class="field"><label>SKU</label><input class="input" v-model="form.sku" required /></div>
          <div class="field"><label>Title</label><input class="input" v-model="form.title" required /></div>
          <div class="field"><label>Price</label><input type="number" min="0" step="0.01" class="input" v-model.number="form.price" required /></div>
          <div class="field"><label>Category</label><input class="input" v-model="form.category" /></div>
        </div>
        <div class="field">
          <label>Description</label>
          <textarea class="textarea" v-model="form.description"></textarea>
        </div>
        <div class="field">
          <label>Tags (comma-separated)</label>
          <input class="input" v-model="tagsText" placeholder="audio, wireless, sale" />
        </div>
        <div class="field">
          <label>Attributes (one key:value per line)</label>
          <textarea class="textarea" v-model="attrsText" placeholder="brand: Acme&#10;color: black"></textarea>
        </div>
        <div class="field">
          <label>Variants</label>
          <div v-for="(v, i) in variants" :key="i" class="variant-row">
            <input class="input" v-model="v.sku" placeholder="Variant SKU" />
            <input class="input" v-model="v.color" placeholder="Color" />
            <input type="number" min="0" class="input" v-model.number="v.stock" placeholder="Stock" />
            <button type="button" class="btn btn-sm btn-danger" @click="variants.splice(i, 1)">✕</button>
          </div>
          <button type="button" class="btn btn-sm" @click="variants.push({ sku: '', color: '', stock: 0 })">
            + Add variant
          </button>
        </div>
        <div class="field checkbox-line">
          <input type="checkbox" id="active" v-model="form.active" />
          <label for="active">Active</label>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? 'Saving…' : (editingId ? 'Update product' : 'Create product') }}
          </button>
          <button v-if="editingId" type="button" class="btn" @click="resetForm">Cancel</button>
        </div>
      </form>
    </div>

    <div class="card">
      <h3>Products</h3>
      <div class="field checkbox-line" style="margin-bottom: 0.75rem">
        <input type="checkbox" id="inclInactive" v-model="includeInactive" @change="load" />
        <label for="inclInactive">Include inactive products</label>
      </div>
      <div v-if="loading" class="loading">Loading…</div>
      <div v-else-if="loadError" class="alert alert-error">{{ loadError }}</div>
      <div v-else-if="products.length === 0" class="empty">No products.</div>
      <table v-else class="tbl">
        <thead>
          <tr><th>Title</th><th>SKU</th><th>Category</th><th>Price</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="p in products" :key="p.id">
            <td>{{ p.title }}</td>
            <td>{{ p.sku }}</td>
            <td>{{ p.category }}</td>
            <td>{{ formatPrice(p.price) }}</td>
            <td>{{ p.active ? 'Yes' : 'No' }}</td>
            <td><button class="btn btn-sm" @click="startEdit(p)">Edit</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'
import { formatPrice } from '../store.js'

const products = ref([])
const loading = ref(false)
const loadError = ref('')
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')
const formOk = ref('')
const includeInactive = ref(false)

const form = ref(blankForm())
const tagsText = ref('')
const attrsText = ref('')
const variants = ref([])

function blankForm() {
  return { sku: '', title: '', description: '', price: 0, category: '', active: true }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    products.value = await api.listProducts(includeInactive.value ? { active: false } : {})
  } catch (e) {
    loadError.value = 'Could not load products: ' + e.message
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  form.value = blankForm()
  tagsText.value = ''
  attrsText.value = ''
  variants.value = []
  formError.value = ''
  formOk.value = ''
}

async function startEdit(p) {
  editingId.value = p.id
  formError.value = ''
  formOk.value = ''
  try {
    const full = await api.getProduct(p.id)
    form.value = {
      sku: full.sku || '',
      title: full.title || '',
      description: full.description || '',
      price: full.price ?? 0,
      category: full.category || '',
      active: full.active !== false
    }
    tagsText.value = (full.tags || []).join(', ')
    attrsText.value = Object.entries(full.attributes || {})
      .map(([k, v]) => `${k}: ${v}`)
      .join('\n')
    variants.value = (full.variants || []).map((v) => ({
      sku: v.sku || '',
      color: v.color || '',
      stock: v.stock ?? 0
    }))
  } catch (e) {
    formError.value = 'Could not load product: ' + e.message
    editingId.value = null
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function parseAttributes() {
  const attrs = {}
  for (const line of attrsText.value.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const idx = t.indexOf(':')
    if (idx === -1) continue
    attrs[t.slice(0, idx).trim()] = t.slice(idx + 1).trim()
  }
  return attrs
}

async function save() {
  saving.value = true
  formError.value = ''
  formOk.value = ''
  const payload = {
    sku: form.value.sku,
    title: form.value.title,
    description: form.value.description,
    price: Number(form.value.price) || 0,
    category: form.value.category,
    active: !!form.value.active,
    tags: tagsText.value.split(',').map((t) => t.trim()).filter(Boolean),
    attributes: parseAttributes(),
    variants: variants.value
      .filter((v) => v.sku || v.color)
      .map((v) => ({ sku: v.sku, color: v.color, stock: Number(v.stock) || 0 }))
  }
  try {
    if (editingId.value) {
      await api.updateProduct(editingId.value, payload)
      formOk.value = 'Product updated.'
    } else {
      await api.createProduct(payload)
      formOk.value = 'Product created.'
    }
    const msg = formOk.value
    resetForm()
    formOk.value = msg
    await load()
  } catch (e) {
    formError.value = 'Save failed: ' + e.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
