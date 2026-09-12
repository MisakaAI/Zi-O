<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { get, post } from './api/client'
import { useI18n } from './i18n'

const site = ref({ site_title: 'ZI/O', site_tagline: '' })
const user = ref(null)
const loading = ref(true)
const error = ref(null)
const { locale, localeOptions, setLocale, t, errorKey } = useI18n()
const displayName = computed(() => user.value?.display_name || '')
const siteTimezone = computed(() => site.value.timezone || 'UTC')
provide('siteTimezone', siteTimezone)
async function loadSession() { try { site.value = await get('/api/public/site'); user.value = (await get('/api/auth/me')).user } catch (err) { error.value = err } finally { loading.value = false } }
async function logout() { await post('/api/auth/logout', {}); user.value = null; window.location.href = '/manage/login' }
onMounted(loadSession)
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <a class="wordmark" href="/now" :aria-label="t('brand.homeLabel')">ZI/O</a>
      <nav :aria-label="t('nav.primary')">
        <RouterLink to="/now">{{ t('nav.now') }}</RouterLink>
        <RouterLink to="/log">{{ t('nav.log') }}</RouterLink>
        <RouterLink to="/index">{{ t('nav.index') }}</RouterLink>
        <RouterLink to="/about">{{ t('nav.about') }}</RouterLink>
      </nav>
      <div class="session-nav">
        <span v-if="displayName" class="mono">{{ displayName }}</span>
        <RouterLink v-if="!displayName" to="/manage/login">{{ t('nav.signIn') }}</RouterLink>
        <button v-else class="link-button" @click="logout">{{ t('nav.signOut') }}</button>
      </div>
      <label class="locale-switcher">
        <span class="sr-only">{{ t('language.label') }}</span>
        <select :value="locale" :aria-label="t('language.label')" @change="setLocale($event.target.value)">
          <option v-for="option in localeOptions" :key="option.value" :value="option.value">{{ t(option.labelKey) }}</option>
        </select>
      </label>
    </header>
    <p v-if="loading" class="sr-only" role="status">{{ t('app.loading') }}</p>
    <p v-if="error" class="global-error" role="alert">{{ t(errorKey(error)) }}</p>
    <main class="page-frame"><RouterView /></main>
    <footer class="footer"><span class="mono">{{ t('footer.archive') }}</span><span>{{ site.site_tagline }}</span></footer>
  </div>
</template>
