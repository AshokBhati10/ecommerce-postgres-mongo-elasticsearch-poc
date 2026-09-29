<template>
  <div class="container">
    <h1 class="page-title">Storefront</h1>

    <div class="card">
      <div class="filters-row">
        <div class="field">
          <label>Category</label>
          <select class="select" v-model="category" @change="onCategoryChange">
            <option value="">All categories</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field search-field">
          <label>Search</label>
          <input class="input" v-model="q" @input="onSearchInput" placeholder="Search products…" />
        </div>
        <div class="field">
          <label>Listing mode</label>
          <button class="btn btn-sm" @click="toggleInfinite">
            {{ infiniteMode ? 'Back to Pagination' : 'Enable Infinite Scrolling' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading products…</div>
    <div v-else-if="error" class="alert alert-error">{{ error }}</div>
    <div v-else-if="products.length === 0" class="empty card">No products found.</div>
    <div v-else>
      <div class="result-meta">
        Showing {{ products.length }} of {{ total }} products
        <span class="es-note">· search powered by Elasticsearch</span>
      </div>
      <div class="grid">
        <div v-for="p in products" :key="p.id" class="card product-card">
          <img class="product-img" :src="p.image_url || FALLBACK_IMG" :alt="p.title"
               loading="lazy" @error="onImgError" />
          <h3>{{ p.title }}</h3>
          <div class="desc">{{ shortDesc(p.description) }}</div>
          <div class="attr-line"><b>Category:</b> {{ p.category }}</div>
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
          <button class="btn btn-primary" @click="handleAddToCart(p)">Add to Cart</button>
        </div>
      </div>
      <div v-if="!infiniteMode && totalPages > 1" class="pagination">
        <button class="btn btn-sm" :disabled="page <= 1 || pageLoading" @click="goToPage(page - 1)">
          ‹ Previous
        </button>
        <button v-for="n in pageNumbers" :key="n" class="btn btn-sm"
                :class="{ 'btn-primary': n === page }" :disabled="n === page || pageLoading"
                @click="goToPage(n)">
          {{ n }}
        </button>
        <button class="btn btn-sm" :disabled="page >= totalPages || pageLoading" @click="goToPage(page + 1)">
          Next ›
        </button>
        <span class="page-info">Page {{ page }} of {{ totalPages }}</span>
      </div>
      <div v-if="infiniteMode && infiniteLoading" class="loading">Loading more products…</div>
      <div v-if="infiniteMode && infiniteDone && products.length > 0" class="end-note">
        You’ve reached the end — all {{ total }} products loaded.
      </div>
    </div>
  </div>

  <!-- Non-blocking cart acknowledgement: appears on add-to-cart, fades away. -->
  <div v-if="toast" class="toast" role="status">{{ toast }}</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client.js'
import { addToCart, formatPrice } from '../store.js'

const PAGE_SIZE = 20

const categories = ref([])
const products = ref([])
const category = ref('')
const q = ref('')
const loading = ref(false)
const error = ref('')
const page = ref(1)
const total = ref(0)
const totalPages = ref(0)
let searchTimer = null

// Optional infinite-scrolling mode. Off by default: normal ES pagination.
// When on, the same backend page API is fetched page-by-page as the user
// scrolls, and results are appended (never fetched all at once).
const infiniteMode = ref(false)
const infiniteLoading = ref(false) // a follow-on page fetch in progress
const infiniteDone = ref(false)    // no more pages left to fetch
const infinitePage = ref(1)        // next page to request in infinite mode
let loadedIds = new Set()          // dedupe guard across appended pages

// Cart acknowledgement toast (auto-dismissed, non-blocking).
const toast = ref('')
let toastTimer = null

function handleAddToCart(p) {
  addToCart(p) // existing cart/quantity logic unchanged
  toast.value = `“${p.title}” added to cart`
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

// Inline SVG placeholder shown when a product image is missing or fails to load.
const FALLBACK_IMG =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">` +
      `<rect width="100%" height="100%" fill="#e5e7eb"/>` +
      `<text x="50%" y="50%" font-family="sans-serif" font-size="26" fill="#9ca3af" ` +
      `text-anchor="middle" dy=".3em">No image</text></svg>`
  )

function onImgError(e) {
  const img = e.target
  if (img.src !== FALLBACK_IMG) img.src = FALLBACK_IMG
}

// Windowed page numbers (current ± 2) for the pagination controls.
const pageNumbers = computed(() => {
  const totalP = totalPages.value
  const cur = page.value
  const start = Math.max(1, Math.min(cur - 2, totalP - 4))
  const end = Math.min(totalP, start + 4)
  const nums = []
  for (let n = start; n <= end; n++) nums.push(n)
  return nums
})

const pageLoading = computed(() => loading.value)

function shortDesc(d) {
  if (!d) return ''
  return d.length > 120 ? d.slice(0, 120) + '…' : d
}

async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listProducts({
      category: category.value,
      q: q.value,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    // Backend returns a paginated envelope when `page` is given.
    if (res && Array.isArray(res.items)) {
      products.value = res.items
      total.value = res.total
      totalPages.value = res.total_pages
      // Clamp if the filter shrank beneath the current page.
      if (page.value > res.total_pages && res.total_pages > 0) {
        page.value = res.total_pages
        await loadProducts()
        return
      }
    } else {
      // Fallback for a plain-list response (older backend).
      products.value = res
      total.value = res.length
      totalPages.value = 1
    }
  } catch (e) {
    error.value = 'Could not load products: ' + e.message
  } finally {
    loading.value = false
  }
}

function goToPage(n) {
  if (n < 1 || n > totalPages.value || n === page.value || loading.value) return
  page.value = n
  loadProducts()
}

function onCategoryChange() {
  if (infiniteMode.value) {
    resetInfinite()
  } else {
    page.value = 1
    loadProducts()
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (infiniteMode.value) {
      resetInfinite()
    } else {
      page.value = 1
      loadProducts()
    }
  }, 350)
}

// --- Infinite scrolling ------------------------------------------------

// Reset the infinite list back to page 1 (fresh query/category), then fetch.
function resetInfinite() {
  loadedIds = new Set()
  products.value = []
  infinitePage.value = 1
  infiniteDone.value = false
  error.value = ''
  loadNextInfinitePage()
}

async function loadNextInfinitePage() {
  // One in-flight request at a time; stop once every page is loaded.
  if (!infiniteMode.value || infiniteLoading.value || infiniteDone.value || loading.value) return
  infiniteLoading.value = true
  try {
    const next = infinitePage.value
    const res = await api.listProducts({
      category: category.value,
      q: q.value,
      page: next,
      page_size: PAGE_SIZE,
    })
    if (res && Array.isArray(res.items)) {
      // Append only products not already shown (dedupe across pages).
      const fresh = res.items.filter((p) => !loadedIds.has(p.id))
      fresh.forEach((p) => loadedIds.add(p.id))
      products.value = [...products.value, ...fresh]
      total.value = res.total
      totalPages.value = res.total_pages
      if (next >= res.total_pages || res.items.length === 0) {
        infiniteDone.value = true
      } else {
        infinitePage.value = next + 1
      }
    } else {
      infiniteDone.value = true
    }
  } catch (e) {
    error.value = 'Could not load products: ' + e.message
    infiniteDone.value = true // stop retrying a failing page on its own
  } finally {
    infiniteLoading.value = false
  }
}

function onScroll() {
  if (!infiniteMode.value) return
  const nearBottom =
    window.innerHeight + window.scrollY >=
    document.documentElement.scrollHeight - 600
  if (nearBottom) loadNextInfinitePage()
}

function toggleInfinite() {
  if (infiniteMode.value) {
    // Back to normal pagination.
    infiniteMode.value = false
    page.value = 1
    loadProducts()
  } else {
    infiniteMode.value = true
    resetInfinite()
  }
}

onMounted(async () => {
  try {
    categories.value = await api.listCategories()
  } catch {
    // categories are optional — storefront works without them
  }
  await loadProducts()
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>
