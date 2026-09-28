<template>
  <div class="container">
    <h1 class="page-title">Checkout</h1>

    <div v-if="success" class="alert alert-success">
      Order <b>#{{ success.id }}</b> placed successfully!
      <span v-if="success.es_synced">Search index is in sync.</span>
      <span v-else>Search sync is pending — the order will appear in admin search shortly.</span>
      <div style="margin-top: 0.5rem">
        <router-link :to="{ name: 'my-orders' }">
          View my orders
        </router-link>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <div v-if="lines.length === 0 && !success" class="card empty">
      Your cart is empty. <router-link to="/">Browse the storefront</router-link>.
    </div>

    <div v-else-if="lines.length > 0" class="card">
      <table class="tbl">
        <thead>
          <tr><th>Product</th><th>Unit price</th><th>Qty</th><th>Line total</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="l in lines" :key="l.product.id">
            <td>{{ l.product.title }}</td>
            <td>{{ formatPrice(l.product.price) }}</td>
            <td>
              <input
                type="number"
                min="0"
                class="input"
                style="width: 70px"
                :value="l.quantity"
                @change="(e) => setQuantity(l.product.id, Number(e.target.value))"
              />
            </td>
            <td>{{ formatPrice(l.product.price * l.quantity) }}</td>
            <td><button class="btn btn-sm" @click="removeFromCart(l.product.id)">Remove</button></td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="3"><b>Total</b></td>
            <td><b>{{ formatPrice(cartTotal) }}</b></td>
            <td></td>
          </tr>
        </tfoot>
      </table>
      <div style="margin-top: 1rem">
        <button class="btn btn-primary" :disabled="!store.user || placing" @click="placeOrder">
          {{ placing ? 'Placing order…' : 'Place Order' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { api } from '../api/client.js'
import { store, setQuantity, removeFromCart, clearCart, cartTotal, formatPrice } from '../store.js'

const lines = computed(() => Object.values(store.cart))
const placing = ref(false)
const error = ref('')
const success = ref(null)

async function placeOrder() {
  if (!store.user) {
    error.value = 'Select a user first.'
    return
  }
  placing.value = true
  error.value = ''
  success.value = null
  try {
    const order = await api.createOrder({
      user_id: store.user.id,
      items: lines.value.map((l) => ({
        product_id: l.product.id,
        quantity: l.quantity
      }))
    })
    success.value = order
    clearCart()
  } catch (e) {
    error.value = 'Order failed: ' + e.message
  } finally {
    placing.value = false
  }
}
</script>
