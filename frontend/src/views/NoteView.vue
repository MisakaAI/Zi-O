<script setup>
import { inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import StateMessage from '../components/StateMessage.vue'
const route = useRoute(); const note = ref(null); const loading = ref(true); const error = ref('')
const siteTimezone = inject('siteTimezone', 'UTC')
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short', timeZone }).format(new Date(value)) }
async function load() { try { note.value = await get(`/api/public/notes/${route.params.id}`) } catch (err) { error.value = err.message } finally { loading.value = false } }; onMounted(load)
</script>
<template><StateMessage v-if="loading" type="loading" message="Opening note…" /><StateMessage v-else-if="error" type="error" :message="error" /><article v-else class="note-detail"><div class="eyebrow mono">{{ note.archive_label }}</div><h1>{{ note.title || 'Untitled event' }}</h1><time class="timestamp mono" :datetime="note.started_at">{{ formatDate(note.started_at) }}<span v-if="note.ended_at"> → {{ formatDate(note.ended_at) }}</span></time><div class="chip-row"><span v-for="item in note.items" :key="item.id" class="chip chip-item">{{ item.title }}</span><RouterLink v-for="tag in note.tags" :key="tag.id" class="chip" :to="`/tag/${tag.slug}`">#{{ tag.name }}</RouterLink></div><div v-if="note.has_static_page" class="static-link"><a :href="note.static_url">OPEN STATIC PAGE ↗</a></div><div class="sanitized-content note-content" v-html="note.content_html_sanitized"></div></article></template>
