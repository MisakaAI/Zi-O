<script setup>
import { onMounted, ref, watch } from 'vue'
import { get } from '../api/client'
import ItemGrid from '../components/ItemGrid.vue'
import TimelineList from '../components/TimelineList.vue'
const props = defineProps({ code: { type: String, required: true } }); const items = ref([]); const notes = ref([]); const nextCursor = ref(null); const loading = ref(true); const error = ref('')
const labels = { JOURNAL: 'Journal', BOOK: 'Books', MOVIE: 'Movies', GAME: 'Games', CODE: 'Code' }
async function load() { loading.value = true; error.value = ''; try { const [itemData, timeline] = await Promise.all([get(`/api/public/items?category=${props.code}`), get(`/api/public/timeline?category=${props.code}&limit=20`)]); items.value = itemData.items; notes.value = timeline.items; nextCursor.value = timeline.next_cursor } catch (err) { error.value = err.message } finally { loading.value = false } }
async function loadMore() { if (!nextCursor.value) return; try { const data = await get(`/api/public/timeline?category=${props.code}&limit=20&cursor=${encodeURIComponent(nextCursor.value)}`); notes.value.push(...data.items); nextCursor.value = data.next_cursor } catch (err) { error.value = err.message } }
watch(() => props.code, load); onMounted(load)
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">INDEX / {{ code }}</div><h1>{{ labels[code] }}</h1><p class="muted">Long-lived context, placed back on the temporal rail.</p></div><div v-if="loading" class="loading-line" role="status">Loading archive…</div><div v-else-if="error" class="inline-error" role="alert">{{ error }}</div><template v-else><h2 class="subheading">Items</h2><ItemGrid :items="items" /><h2 class="subheading">Events</h2><TimelineList :notes="notes" :next-cursor="nextCursor" @load-more="loadMore" /></template></section></template>
