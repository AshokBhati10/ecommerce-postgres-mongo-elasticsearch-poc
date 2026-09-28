<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="login-logo">🛍</span>
        <span class="login-name">OneStop</span>
      </div>
      <h1 class="login-title">Welcome to OneStop</h1>
      <p class="login-subtitle">Select your account to continue</p>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <label class="login-label" for="account-select">Account</label>
      <select id="account-select" class="select login-select" v-model="selectedId">
        <option value="" disabled>Choose an account…</option>
        <option v-for="u in users" :key="u.id" :value="String(u.id)">
          {{ u.name }} — {{ roleLabel(u.role) }}
        </option>
      </select>

      <button class="btn btn-primary login-btn" :disabled="!selectedId || signingIn" @click="signIn">
        {{ signingIn ? 'Signing in…' : 'Continue' }}
      </button>

      <p class="login-hint">Demo only — this is simulated account selection, not real authentication.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client.js'
import { setUser, roleLabel } from '../store.js'

const router = useRouter()
const users = ref([])
const selectedId = ref('')
const signingIn = ref(false)
const error = ref('')

async function signIn() {
  const user = users.value.find((u) => String(u.id) === selectedId.value)
  if (!user) return
  signingIn.value = true
  try {
    setUser(user) // stores the user and normalizes the role
    await router.push({ name: 'storefront' })
  } finally {
    signingIn.value = false
  }
}

onMounted(async () => {
  try {
    users.value = await api.listUsers()
  } catch (e) {
    error.value = 'Could not load accounts: ' + e.message
  }
})
</script>
