<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const notes = ref([]); const cursor = ref(null); const loading = ref(true); const error = ref(null)
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
const groups = computed(() => {
  const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value
  const keyFormatter = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone })
  const grouped = []
  for (const note of notes.value) {
    const key = keyFormatter.format(new Date(note.started_at))
    let group = grouped.find(item => item.key === key)
    if (!group) { group = { key, label: d(note.started_at, { dateStyle: 'full' }, timeZone), notes: [] }; grouped.push(group) }
    group.notes.push(note)
  }
  return grouped
})
async function load(more = false) { loading.value = true; error.value = null; try { const q = new URLSearchParams({ limit: '20' }); if (more && cursor.value) q.set('cursor', cursor.value); const data = await get(`/api/public/timeline?${q}`); notes.value = more ? [...notes.value, ...data.items] : data.items; cursor.value = data.next_cursor } catch (err) { error.value = err } finally { loading.value = false } }
onMounted(() => load())
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">{{ t('log.eyebrow') }}</div><h1>{{ t('log.title') }}</h1><p class="muted">{{ t('log.description') }}</p></div><StateMessage v-if="loading && !notes.length" type="loading" :message="t('state.readingArchive')" /><StateMessage v-else-if="error && !notes.length" type="error" :message="localizedError" /><StateMessage v-else-if="!notes.length" type="empty" :message="t('state.noPublicEvents')" /><div v-else class="log-groups"><section v-for="group in groups" :key="group.key" class="date-group"><h2><time :datetime="group.key" class="mono">{{ group.label }}</time></h2><TimelineList :notes="group.notes" /></section><button v-if="cursor" class="load-more" :disabled="loading" @click="load(true)">{{ loading ? t('state.loading') : t('common.loadOlder') }}</button><p v-if="error" class="inline-error" role="alert">{{ localizedError }}</p></div></section></template>
