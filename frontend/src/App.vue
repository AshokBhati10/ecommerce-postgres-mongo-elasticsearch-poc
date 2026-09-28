<template>
  <TopNav v-if="store.user" />
  <router-view />
</template>

<script setup>
import { store } from './store.js'
import TopNav from './components/TopNav.vue'
</script>
