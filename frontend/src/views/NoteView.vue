<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const route = useRoute(); const note = ref(null); const loading = ref(true); const error = ref(null)
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return d(value, { dateStyle: 'full', timeStyle: 'short' }, timeZone) }
async function load() { try { note.value = await get(`/api/public/notes/${route.params.id}`) } catch (err) { error.value = err } finally { loading.value = false } }; onMounted(load)
</script>
<template><StateMessage v-if="loading" type="loading" :message="t('state.openingNote')" /><StateMessage v-else-if="error" type="error" :message="localizedError" /><article v-else class="note-detail"><RouterLink to="/log" class="detail-back">{{ t('common.backToLog') }}</RouterLink><div class="eyebrow mono">{{ note.archive_label }}</div><h1>{{ note.title || t('common.untitledEvent') }}</h1><time class="timestamp mono" :datetime="note.started_at">{{ formatDate(note.started_at) }}</time><span v-if="note.ended_at" class="timestamp mono"> → <time :datetime="note.ended_at">{{ formatDate(note.ended_at) }}</time></span><div class="chip-row"><RouterLink v-for="item in note.items" :key="item.id" class="chip chip-item" :to="`/items/${item.id}`">{{ item.title }}</RouterLink><RouterLink v-for="tag in note.tags" :key="tag.id" class="chip" :to="`/tag/${tag.slug}`">#{{ tag.name }}</RouterLink></div><div v-if="note.has_static_page" class="static-link"><a :href="note.static_url">{{ t('note.staticPage') }} ↗</a></div><div class="sanitized-content note-content" v-html="note.content_html_sanitized"></div></article></template>
