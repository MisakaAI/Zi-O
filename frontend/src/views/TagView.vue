<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
const route = useRoute(); const data = ref(null); const loading = ref(true); const error = ref('')
onMounted(async () => { try { data.value = await get(`/api/public/tags/${encodeURIComponent(route.params.slug)}`) } catch (err) { error.value = err.message } finally { loading.value = false } })
async function loadMore() { if (!data.value?.next_cursor) return; try { const next = await get(`/api/public/tags/${encodeURIComponent(route.params.slug)}?cursor=${encodeURIComponent(data.value.next_cursor)}`); data.value.items.push(...next.items); data.value.next_cursor = next.next_cursor } catch (err) { error.value = err.message } }
</script>
<template><section><StateMessage v-if="loading" type="loading" message="Reading tag…" /><StateMessage v-else-if="error" type="error" :message="error" /><template v-else><div class="section-heading"><div class="eyebrow mono">TAG / {{ data.tag.slug }}</div><h1>#{{ data.tag.name }}</h1></div><TimelineList :notes="data.items" :next-cursor="data.next_cursor" @load-more="loadMore" /></template></section></template>
