<template>
  <nav class="nav">
    <router-link to="/" class="brand">Shop</router-link>
    <router-link to="/">Storefront</router-link>
    <router-link to="/checkout">
      Checkout
      <span v-if="cartCount" class="cart-pill">{{ cartCount }}</span>
    </router-link>
    <router-link to="/admin">Admin Search</router-link>
    <router-link to="/admin/catalog">Catalog</router-link>
    <span class="spacer"></span>
    <span class="user-badge" v-if="store.user">
      Logged in as <b>{{ store.user.name }}</b>
    </span>
    <span class="user-badge" v-else>Guest — pick a user on the storefront</span>
  </nav>
</template>

<script setup>
import { store, cartCount } from '../store.js'
</script>
