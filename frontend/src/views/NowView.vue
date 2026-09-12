<script setup>
import { inject, onMounted, onUnmounted, ref } from 'vue'
import { get } from '../api/client'
import NoteCard from '../components/NoteCard.vue'
import StateMessage from '../components/StateMessage.vue'
const data = ref(null); const loading = ref(true); const error = ref(''); const clock = ref(new Date()); let timer
const siteTimezone = inject('siteTimezone', 'UTC')
function clockText() { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return clock.value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone }) }
async function load() { try { data.value = await get('/api/public/now') } catch (err) { error.value = err.message } finally { loading.value = false } }
onMounted(() => { load(); timer = setInterval(() => { clock.value = new Date() }, 60000) })
onUnmounted(() => clearInterval(timer))
</script>
<template><section class="hero-page"><div class="eyebrow mono">CURRENT SLICE / NOW</div><div class="now-grid"><div><p class="now-clock mono"><time :datetime="clock.toISOString()">{{ clockText() }}</time></p><p class="muted">{{ data?.timezone || 'UTC' }}</p></div><div class="signal-panel"><span class="signal-dot" aria-hidden="true"></span><div><span class="eyebrow mono">SIGNAL</span><p v-if="data?.status">{{ data.status }}</p><p v-else class="muted">No status signal set.</p><NoteCard v-if="data?.current_signal" :note="data.current_signal" /></div></div></div><StateMessage v-if="loading" type="loading" message="Synchronizing now…" /><StateMessage v-else-if="error" type="error" :message="error" /><template v-else><div class="section-heading"><span class="eyebrow mono">{{ data.recent_mode === 'today' ? 'TODAY' : 'RECENT' }}</span><h1>Recent events</h1></div><div class="timeline compact"><NoteCard v-for="note in data.recent_notes" :key="note.id" :note="note" /></div><StateMessage v-if="!data.recent_notes.length" type="empty" message="No public events yet." /></template></section></template>
