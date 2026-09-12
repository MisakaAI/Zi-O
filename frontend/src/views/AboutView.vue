<script setup>
import { onMounted, ref } from 'vue'
import { get } from '../api/client'
import StateMessage from '../components/StateMessage.vue'
const site = ref(null); const loading = ref(true); const error = ref('')
onMounted(async () => { try { site.value = await get('/api/public/site') } catch (err) { error.value = err.message } finally { loading.value = false } })
</script>
<template><section class="prose-page"><div class="eyebrow mono">ABOUT / ZI/O</div><h1>{{ site?.site_title || 'ZI/O' }}</h1><p class="lead">{{ site?.site_tagline }}</p><StateMessage v-if="loading" type="loading" message="Loading note…" /><StateMessage v-else-if="error" type="error" :message="error" /><div v-else class="sanitized-content" v-html="site.about_html_sanitized"></div></section></template>

