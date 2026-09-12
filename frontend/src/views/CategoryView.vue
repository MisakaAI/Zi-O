<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get } from '../api/client'
import ItemGrid from '../components/ItemGrid.vue'
import TimelineList from '../components/TimelineList.vue'
import { useI18n } from '../i18n'
const props = defineProps({ code: { type: String, required: true } }); const items = ref([]); const notes = ref([]); const nextCursor = ref(null); const loading = ref(true); const error = ref(null)
const { t, categoryLabel, errorKey } = useI18n()
const pageTitle = computed(() => categoryLabel(props.code, props.code))
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
async function load() { loading.value = true; error.value = null; try { const [itemData, timeline] = await Promise.all([get(`/api/public/items?category=${props.code}`), get(`/api/public/timeline?category=${props.code}&limit=20`)]); items.value = itemData.items; notes.value = timeline.items; nextCursor.value = timeline.next_cursor } catch (err) { error.value = err } finally { loading.value = false } }
async function loadMore() { if (!nextCursor.value) return; try { const data = await get(`/api/public/timeline?category=${props.code}&limit=20&cursor=${encodeURIComponent(nextCursor.value)}`); notes.value.push(...data.items); nextCursor.value = data.next_cursor } catch (err) { error.value = err } }
watch(() => props.code, load); onMounted(load)
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">{{ t('category.eyebrow', { code }) }}</div><h1>{{ pageTitle }}</h1><p class="muted">{{ t('category.description') }}</p></div><div v-if="loading" class="loading-line" role="status">{{ t('state.readingArchive') }}</div><div v-else-if="error" class="inline-error" role="alert">{{ localizedError }}</div><template v-else><h2 class="subheading">{{ t('category.items') }}</h2><ItemGrid :items="items" /><h2 class="subheading">{{ t('category.events') }}</h2><TimelineList :notes="notes" :next-cursor="nextCursor" @load-more="loadMore" /></template></section></template>
