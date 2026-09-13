<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get } from '../api/client'
import ItemGrid from '../components/ItemGrid.vue'
import StateMessage from '../components/StateMessage.vue'
import TimelineList from '../components/TimelineList.vue'
import { useI18n } from '../i18n'
const props = defineProps({ code: { type: String, required: true } }); const items = ref([]); const notes = ref([]); const nextCursor = ref(null); const loading = ref(true); const error = ref(null)
const loadingMore = ref(false); const moreError = ref(null)
const { t, categoryLabel, errorKey } = useI18n()
const pageTitle = computed(() => categoryLabel(props.code, props.code))
const localizedMoreError = computed(() => moreError.value ? t(errorKey(moreError.value)) : '')
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
async function load() { loading.value = true; error.value = null; try { const [itemData, timeline] = await Promise.all([get(`/api/public/items?category=${props.code}`), get(`/api/public/timeline?category=${props.code}&limit=20`)]); items.value = itemData.items; notes.value = timeline.items; nextCursor.value = timeline.next_cursor } catch (err) { error.value = err } finally { loading.value = false } }
async function loadMore() { if (!nextCursor.value) return; if (loadingMore.value) return; loadingMore.value = true; moreError.value = null; try { const data = await get(`/api/public/timeline?category=${props.code}&limit=20&cursor=${encodeURIComponent(nextCursor.value)}`); notes.value.push(...data.items); nextCursor.value = data.next_cursor } catch (err) { moreError.value = err } finally { loadingMore.value = false } }
watch(() => props.code, load); onMounted(load)
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">{{ t('category.eyebrow', { code }) }}</div><h1>{{ pageTitle }}</h1><p class="muted">{{ t('category.description') }}</p></div><StateMessage v-if="loading" type="loading" :message="t('state.readingArchive')" /><StateMessage v-else-if="error" type="error" :message="localizedError" /><template v-else><h2 class="subheading">{{ t('category.items') }}</h2><ItemGrid :items="items" /><h2 class="subheading">{{ t('category.events') }}</h2><TimelineList :notes="notes" :next-cursor="nextCursor" :loading="loadingMore" :error="localizedMoreError" @load-more="loadMore" /></template></section></template>
