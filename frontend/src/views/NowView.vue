<script setup>
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { get } from '../api/client'
import CalendarCard from '../components/CalendarCard.vue'
import NoteCard from '../components/NoteCard.vue'
import ReferenceIndex from '../components/ReferenceIndex.vue'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const data = ref(null)
const loading = ref(true)
const error = ref(null)
const clock = ref(new Date())
let timer
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t, errorKey } = useI18n()
const timezone = computed(() => data.value?.timezone || (typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value) || 'UTC')
async function load() { try { data.value = await get('/api/public/now') } catch (err) { error.value = err } finally { loading.value = false } }
onMounted(() => { load(); timer = setInterval(() => { clock.value = new Date() }, 60000) })
onUnmounted(() => clearInterval(timer))
</script>
<template>
  <section class="hero-page">
    <div class="now-grid">
      <div class="now-intro">
        <div class="eyebrow mono">{{ t('now.eyebrow') }}</div>
        <h1>{{ t('now.title') }}</h1>
        <p class="lead">{{ t('now.description') }}</p>
        <div class="now-clock">
          <time class="clock-value mono" :datetime="clock.toISOString()">{{ d(clock, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }, timezone) }}</time>
          <time class="clock-date mono" :datetime="clock.toISOString()">{{ d(clock, { month: 'short', day: 'numeric', weekday: 'short' }, timezone) }}</time>
          <span class="clock-zone mono">{{ timezone }}</span>
        </div>
        <StateMessage v-if="loading" type="loading" :message="t('state.synchronizingNow')" />
        <StateMessage v-else-if="error" type="error" :message="t(errorKey(error))" />
        <div v-else class="signal-panel">
          <span class="signal-label mono"><span class="signal-dot" aria-hidden="true"></span>{{ t('now.signal') }}</span>
          <p class="signal-status" :class="{ muted: !data.status }">{{ data.status || t('state.noStatus') }}</p>
          <RouterLink v-if="data.current_signal" class="signal-note" :to="`/n/${data.current_signal.id}`">
            <span class="mono">{{ data.current_signal.archive_label }}</span><span>{{ data.current_signal.title || t('common.untitledEvent') }}</span><span aria-hidden="true">↗</span>
          </RouterLink>
        </div>
      </div>
      <CalendarCard :reference-date="clock.toISOString()" :timezone="timezone" />
    </div>
    <section v-if="data" aria-labelledby="recent-title">
      <div class="section-topline">
        <div><span class="eyebrow mono">{{ data.recent_mode === 'today' ? t('now.today') : t('now.recent') }}</span><h2 id="recent-title">{{ t('now.recentEvents') }}</h2></div>
        <RouterLink class="text-link" to="/log">{{ t('now.viewLog') }} <span aria-hidden="true">↗</span></RouterLink>
      </div>
      <div v-if="data.recent_notes.length" class="timeline compact"><NoteCard v-for="note in data.recent_notes" :key="note.id" :note="note" /></div>
      <StateMessage v-else type="empty" :message="t('state.noPublicEvents')" />
    </section>
    <ReferenceIndex class="now-reference-index" embedded />
  </section>
</template>
