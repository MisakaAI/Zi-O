<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
const notes = ref([]); const cursor = ref(null); const loading = ref(true); const error = ref('')
const siteTimezone = inject('siteTimezone', 'UTC')
const groups = computed(() => {
  const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value
  const formatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeZone })
  const keyFormatter = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone })
  const grouped = []
  for (const note of notes.value) {
    const key = keyFormatter.format(new Date(note.started_at))
    let group = grouped.find(item => item.key === key)
    if (!group) { group = { key, label: formatter.format(new Date(note.started_at)), notes: [] }; grouped.push(group) }
    group.notes.push(note)
  }
  return grouped
})
async function load(more = false) { loading.value = true; error.value = ''; try { const q = new URLSearchParams({ limit: '20' }); if (more && cursor.value) q.set('cursor', cursor.value); const data = await get(`/api/public/timeline?${q}`); notes.value = more ? [...notes.value, ...data.items] : data.items; cursor.value = data.next_cursor } catch (err) { error.value = err.message } finally { loading.value = false } }
onMounted(() => load())
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">ARCHIVE / LOG</div><h1>Events in their actual time.</h1><p class="muted">A stable rail ordered by started time, with archive numbers that never move.</p></div><StateMessage v-if="loading && !notes.length" type="loading" message="Reading the archive…" /><StateMessage v-else-if="error && !notes.length" type="error" :message="error" /><StateMessage v-else-if="!notes.length" type="empty" message="No public events yet." /><div v-else class="log-groups"><section v-for="group in groups" :key="group.key" class="date-group"><h2><time :datetime="group.key" class="mono">{{ group.label }}</time></h2><TimelineList :notes="group.notes" /></section><button v-if="cursor" class="load-more" :disabled="loading" @click="load(true)">{{ loading ? 'LOADING…' : 'LOAD OLDER' }}</button><p v-if="error" class="inline-error" role="alert">{{ error }}</p></div></section></template>
