<script setup>
import { inject } from 'vue'
defineProps({ items: { type: Array, default: () => [] } })
const siteTimezone = inject('siteTimezone', 'UTC')
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone }).format(new Date(value)) }
</script>
<template><div v-if="items.length" class="item-grid"><RouterLink v-for="item in items" :key="item.id" class="item-tile" :to="`/items/${item.id}`"><div class="poster-frame"><img v-if="item.poster_url" :src="item.poster_url" :alt="`${item.title} poster`" loading="lazy"><span v-else class="poster-placeholder mono">{{ item.category_code }}</span></div><h3>{{ item.title }}</h3><p>{{ item.creator || item.subtitle }}</p><time class="mono" :datetime="item.activity_at || item.created_at">{{ formatDate(item.activity_at || item.created_at) }}</time></RouterLink></div><div v-else class="empty-inline">No public items in this category.</div></template>
