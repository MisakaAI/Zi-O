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
const { t, errorKey } = useI18n()
const timezone = computed(() => data.value?.timezone || (typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value) || 'UTC')
async function load() { try { data.value = await get('/api/public/now') } catch (err) { error.value = err } finally { loading.value = false } }
onMounted(() => { load(); timer = setInterval(() => { clock.value = new Date() }, 60000) })
onUnmounted(() => clearInterval(timer))
</script>
<template>
  <section class="hero-page">
    <div class="eyebrow mono">{{ t('now.eyebrow') }}</div>
    <div class="now-grid">
      <CalendarCard :reference-date="clock.toISOString()" :timezone="timezone" />
      <div class="signal-panel">
        <span class="signal-dot" aria-hidden="true"></span>
        <div>
          <span class="eyebrow mono">{{ t('now.signal') }}</span>
          <p v-if="data?.status">{{ data.status }}</p>
          <p v-else class="muted">{{ t('state.noStatus') }}</p>
          <NoteCard v-if="data?.current_signal" :note="data.current_signal" />
        </div>
      </div>
    </div>
    <StateMessage v-if="loading" type="loading" :message="t('state.synchronizingNow')" />
    <StateMessage v-else-if="error" type="error" :message="t(errorKey(error))" />
    <template v-else>
      <div class="section-heading">
        <span class="eyebrow mono">{{ data.recent_mode === 'today' ? t('now.today') : t('now.recent') }}</span>
        <h1>{{ t('now.recentEvents') }}</h1>
      </div>
      <div class="timeline compact">
        <NoteCard v-for="note in data.recent_notes" :key="note.id" :note="note" />
      </div>
      <StateMessage v-if="!data.recent_notes.length" type="empty" :message="t('state.noPublicEvents')" />
      <ReferenceIndex class="now-reference-index" />
    </template>
  </section>
</template>
