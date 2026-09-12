<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { get, post } from './api/client'

const site = ref({ site_title: 'ZI/O', site_tagline: '' })
const user = ref(null)
const loading = ref(true)
const error = ref('')
const displayName = computed(() => user.value?.display_name || '')
const siteTimezone = computed(() => site.value.timezone || 'UTC')
provide('siteTimezone', siteTimezone)
async function loadSession() { try { site.value = await get('/api/public/site'); user.value = (await get('/api/auth/me')).user } catch (err) { error.value = err.message } finally { loading.value = false } }
async function logout() { await post('/api/auth/logout', {}); user.value = null; window.location.href = '/manage/login' }
onMounted(loadSession)
</script>
<template>
  <div class="app-shell">
    <header class="topbar"><a class="wordmark" href="/now" aria-label="ZI/O home">ZI/O</a><nav aria-label="Primary navigation"><RouterLink to="/now">NOW</RouterLink><RouterLink to="/log">LOG</RouterLink><RouterLink to="/index">INDEX</RouterLink><RouterLink to="/about">ABOUT</RouterLink></nav><div class="session-nav"><span v-if="displayName" class="mono">{{ displayName }}</span><RouterLink v-if="!displayName" to="/manage/login">SIGN IN</RouterLink><button v-else class="link-button" @click="logout">SIGN OUT</button></div></header>
    <p v-if="loading" class="sr-only" role="status">Loading</p><p v-if="error" class="global-error" role="alert">{{ error }}</p><main class="page-frame"><RouterView /></main><footer class="footer"><span class="mono">TEMPORAL ARCHIVE / 0.1</span><span>{{ site.site_tagline }}</span></footer>
  </div>
</template>
