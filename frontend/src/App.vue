<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { RiGithubFill, RiTranslate } from '@remixicon/vue'
import { get, post } from './api/client'
import { useI18n } from './i18n'

const site = ref({ site_title: 'ZI/O', site_tagline: '' })
const user = ref(null)
const loading = ref(true)
const error = ref(null)
const signingOut = ref(false)
const { locale, setLocale, t, errorKey } = useI18n()
const displayName = computed(() => user.value?.display_name || '')
const siteTimezone = computed(() => site.value.timezone || 'UTC')
provide('siteTimezone', siteTimezone)
async function refreshSession() { user.value = (await get('/api/auth/me')).user }
provide('refreshSession', refreshSession)
async function loadSession() { try { site.value = await get('/api/public/site'); await refreshSession() } catch (err) { error.value = err } finally { loading.value = false } }
async function logout() {
  signingOut.value = true; error.value = null
  try { await post('/api/auth/logout', {}); user.value = null; window.location.href = '/manage/login' }
  catch (err) { error.value = err }
  finally { signingOut.value = false }
}
function closeSessionMenu(event) { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() }
function toggleLocale() { setLocale(locale.value === 'zh-CN' ? 'en-US' : 'zh-CN') }
onMounted(loadSession)
</script>
<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">{{ t('nav.skipToContent') }}</a>
    <header class="topbar">
      <RouterLink class="brand" to="/now" :aria-label="t('brand.homeLabel')"><span class="wordmark">ZI/O</span><span class="brand-caption mono">{{ t('brand.caption') }}</span></RouterLink>
      <nav class="primary-nav" :aria-label="t('nav.primary')">
        <RouterLink to="/now">{{ t('nav.now') }}</RouterLink>
        <RouterLink to="/log">{{ t('nav.log') }}</RouterLink>
        <RouterLink to="/index">{{ t('nav.index') }}</RouterLink>
        <RouterLink v-if="displayName" to="/manage">{{ t('nav.manage') }}</RouterLink>
        <RouterLink to="/about">{{ t('nav.about') }}</RouterLink>
      </nav>
      <a class="github-link" href="https://github.com/MisakaAI/Zi-O" target="_blank" rel="noopener noreferrer" :aria-label="t('nav.github')" :title="t('nav.github')">
        <RiGithubFill className="github-icon" aria-hidden="true" focusable="false" />
      </a>
      <button type="button" class="locale-switcher" :aria-label="t('language.switch')" :title="t('language.switch')" @click="toggleLocale">
        <RiTranslate className="locale-icon" aria-hidden="true" focusable="false" />
        <span class="mono">{{ locale === 'zh-CN' ? 'EN' : '中' }}</span>
      </button>
      <div class="session-nav">
        <details v-if="displayName" class="session-menu" @keydown.esc.prevent="closeSessionMenu">
          <summary class="session-trigger mono">{{ displayName }}</summary>
          <div class="session-popover">
            <button type="button" class="link-button session-logout" :disabled="signingOut" @click="logout">{{ t('nav.signOut') }}</button>
          </div>
        </details>
        <RouterLink v-else to="/manage/login">{{ t('nav.signIn') }}</RouterLink>
      </div>
    </header>
    <p v-if="loading" class="sr-only" role="status">{{ t('app.loading') }}</p>
    <p v-if="error" class="global-error" role="alert">{{ t(errorKey(error)) }}</p>
    <main id="main-content" class="page-frame" tabindex="-1"><RouterView :key="$route.path" /></main>
    <footer class="footer"><span class="mono"><span class="footer-mark" aria-hidden="true">/</span> {{ t('footer.archive') }}</span><span>{{ site.site_tagline || t('footer.tagline') }}</span><RouterLink to="/about">{{ t('nav.about') }} <span aria-hidden="true">↗</span></RouterLink></footer>
  </div>
</template>
