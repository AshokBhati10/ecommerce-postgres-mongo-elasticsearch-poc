<template>
  <nav class="nav">
    <router-link to="/" class="brand"><span class="brand-mark">🛍</span> OneStop</router-link>
    <router-link to="/">Storefront</router-link>
    <template v-if="isCustomer">
      <router-link to="/checkout">
        Checkout
        <span v-if="cartCount" class="cart-pill">{{ cartCount }}</span>
      </router-link>
      <router-link to="/orders">My Orders</router-link>
    </template>
    <template v-if="isAdmin">
      <router-link to="/admin">Admin Search</router-link>
      <router-link to="/admin/catalog">Catalog</router-link>
    </template>
    <span class="spacer"></span>
    <span class="user-badge" v-if="store.user">
      <span class="user-identity">
        <span class="user-name">{{ store.user.name }}</span>
        <span class="user-role">{{ roleLabel(store.user.role) }}</span>
      </span>
      <button class="btn btn-sm btn-ghost" @click="switchAccount">Switch Account</button>
    </span>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { store, cartCount, isAdmin, isCustomer, logout, roleLabel } from '../store.js'

const router = useRouter()

function switchAccount() {
  logout()
  router.push({ name: 'login' })
}
</script>
