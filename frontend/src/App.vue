<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { RiGithubFill, RiTranslate } from '@remixicon/vue'
import { get, post } from './api/client'
import { useI18n } from './i18n'

const site = ref({ site_title: 'ZI/O', site_tagline: '' })
const user = ref(null)
const loading = ref(true)
const error = ref(null)
const { locale, setLocale, t, errorKey } = useI18n()
const displayName = computed(() => user.value?.display_name || '')
const siteTimezone = computed(() => site.value.timezone || 'UTC')
provide('siteTimezone', siteTimezone)
async function loadSession() { try { site.value = await get('/api/public/site'); user.value = (await get('/api/auth/me')).user } catch (err) { error.value = err } finally { loading.value = false } }
async function logout() { await post('/api/auth/logout', {}); user.value = null; window.location.href = '/manage/login' }
function toggleLocale() { setLocale(locale.value === 'zh-CN' ? 'en-US' : 'zh-CN') }
onMounted(loadSession)
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <a class="wordmark" href="/now" :aria-label="t('brand.homeLabel')">ZI/O</a>
      <nav :aria-label="t('nav.primary')">
        <RouterLink to="/now">{{ t('nav.now') }}</RouterLink>
        <RouterLink to="/log">{{ t('nav.log') }}</RouterLink>
        <RouterLink to="/about">{{ t('nav.about') }}</RouterLink>
      </nav>
      <a class="github-link" href="https://github.com/MisakaAI/Zi-O" target="_blank" rel="noopener noreferrer" :aria-label="t('nav.github')" :title="t('nav.github')">
        <RiGithubFill className="github-icon" aria-hidden="true" focusable="false" />
      </a>
      <button type="button" class="locale-switcher" :aria-label="t('language.switch')" :title="t('language.switch')" @click="toggleLocale">
        <RiTranslate className="locale-icon" aria-hidden="true" focusable="false" />
      </button>
      <div class="session-nav">
        <div v-if="displayName" class="session-menu">
          <span class="session-trigger mono" tabindex="0">{{ displayName }}</span>
          <div class="session-popover">
            <button type="button" class="link-button session-logout" @click="logout">{{ t('nav.signOut') }}</button>
          </div>
        </div>
        <RouterLink v-else to="/manage/login">{{ t('nav.signIn') }}</RouterLink>
      </div>
    </header>
    <p v-if="loading" class="sr-only" role="status">{{ t('app.loading') }}</p>
    <p v-if="error" class="global-error" role="alert">{{ t(errorKey(error)) }}</p>
    <main class="page-frame"><RouterView /></main>
    <footer class="footer"><span class="mono">{{ t('footer.archive') }}</span><span>{{ site.site_tagline }}</span></footer>
  </div>
</template>
