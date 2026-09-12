<script setup>
import { inject } from 'vue'
import { useI18n } from '../i18n'
defineProps({ items: { type: Array, default: () => [] } })
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t } = useI18n()
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return d(value, { dateStyle: 'medium' }, timeZone) }
</script>
<template><div v-if="items.length" class="item-grid"><RouterLink v-for="item in items" :key="item.id" class="item-tile" :to="`/items/${item.id}`"><div class="poster-frame"><img v-if="item.poster_url" :src="item.poster_url" :alt="t('item.posterAlt', { title: item.title })" loading="lazy"><span v-else class="poster-placeholder mono">{{ item.category_code }}</span></div><h3>{{ item.title }}</h3><p>{{ item.creator || item.subtitle }}</p><time class="mono" :datetime="item.activity_at || item.created_at">{{ formatDate(item.activity_at || item.created_at) }}</time></RouterLink></div><div v-else class="empty-inline">{{ t('state.noPublicItems') }}</div></template>
