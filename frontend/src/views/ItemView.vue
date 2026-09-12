<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const route = useRoute(); const item = ref(null); const loading = ref(true); const error = ref(null)
const { t, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
async function load() { try { item.value = await get(`/api/public/items/${route.params.id}`) } catch (err) { error.value = err } finally { loading.value = false } }
async function loadMore() { if (!item.value?.timeline?.next_cursor) return; try { const next = await get(`/api/public/items/${route.params.id}?cursor=${encodeURIComponent(item.value.timeline.next_cursor)}`); item.value.timeline.items.push(...next.timeline.items); item.value.timeline.next_cursor = next.timeline.next_cursor } catch (err) { error.value = err } }
onMounted(load)
</script>
<template><StateMessage v-if="loading" type="loading" :message="t('state.openingItem')" /><StateMessage v-else-if="error" type="error" :message="localizedError" /><section v-else class="detail-page"><div class="detail-head"><div class="poster-frame large"><img v-if="item.poster_url" :src="item.poster_url" :alt="t('item.posterAlt', { title: item.title })"><span v-else class="poster-placeholder mono">{{ item.category_code }}</span></div><div><div class="eyebrow mono">{{ t('item.eyebrow', { code: item.category_code }) }}</div><h1>{{ item.title }}</h1><p class="lead">{{ item.subtitle }}</p><p class="muted">{{ item.creator }}</p></div></div><h2 class="subheading">{{ t('item.associatedEvents') }}</h2><TimelineList :notes="item.timeline.items" :next-cursor="item.timeline.next_cursor" :loading="false" @load-more="loadMore" /></section></template>
