<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
const route = useRoute(); const data = ref(null); const loading = ref(true); const error = ref('')
async function load(slug) {
  data.value = null; loading.value = true; error.value = ''
  try {
    const result = await get(`/api/public/tags/${encodeURIComponent(slug)}`)
    if (route.params.slug === slug) data.value = result
  } catch (err) {
    if (route.params.slug === slug) error.value = err.message
  } finally {
    if (route.params.slug === slug) loading.value = false
  }
}
watch(() => route.params.slug, load, { immediate: true })
async function loadMore() { if (!data.value?.next_cursor) return; try { const next = await get(`/api/public/tags/${encodeURIComponent(route.params.slug)}?cursor=${encodeURIComponent(data.value.next_cursor)}`); data.value.items.push(...next.items); data.value.next_cursor = next.next_cursor } catch (err) { error.value = err.message } }
</script>
<template><section><StateMessage v-if="loading" type="loading" message="Reading tag…" /><StateMessage v-else-if="error" type="error" :message="error" /><template v-else><div class="section-heading"><div class="eyebrow mono">TAG / {{ data.tag.slug }}</div><h1>#{{ data.tag.name }}</h1></div><TimelineList :notes="data.items" :next-cursor="data.next_cursor" @load-more="loadMore" /></template></section></template>
