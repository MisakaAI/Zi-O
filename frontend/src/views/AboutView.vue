<script setup>
import { computed, onMounted, ref } from 'vue'
import { get } from '../api/client'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const site = ref(null); const loading = ref(true); const error = ref(null)
const { t, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
onMounted(async () => { try { site.value = await get('/api/public/site') } catch (err) { error.value = err } finally { loading.value = false } })
</script>
<template><section class="prose-page"><div class="eyebrow mono">{{ t('about.eyebrow') }}</div><h1>{{ site?.site_title || t('brand.name') }}</h1><p class="lead">{{ site?.site_tagline }}</p><StateMessage v-if="loading" type="loading" :message="t('state.loadingAbout')" /><StateMessage v-else-if="error" type="error" :message="localizedError" /><div v-else class="sanitized-content" v-html="site.about_html_sanitized"></div></section></template>
