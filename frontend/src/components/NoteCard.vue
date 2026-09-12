<script setup>
import { inject } from 'vue'
defineProps({ note: { type: Object, required: true } })
const siteTimezone = inject('siteTimezone', 'UTC')
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone }).format(new Date(value)) }
</script>
<template><article class="note-card"><div class="note-rail"><span class="rail-tick"></span><time class="timestamp mono" :datetime="note.started_at">{{ formatDate(note.started_at) }}</time></div><div class="note-body"><div class="note-kicker mono"><span>{{ note.archive_label }}</span><span v-for="item in note.items" :key="`i${item.id}`" class="chip chip-item">{{ item.title }}</span><RouterLink v-for="tag in note.tags" :key="`t${tag.id}`" class="chip" :to="`/tag/${tag.slug}`">#{{ tag.name }}</RouterLink></div><h3><RouterLink :to="`/n/${note.id}`">{{ note.title || 'Untitled event' }}</RouterLink></h3><div class="note-excerpt sanitized-content" v-if="note.content_html_sanitized" v-html="note.content_html_sanitized"></div><RouterLink class="permalink" :to="`/n/${note.id}`">OPEN NOTE <span aria-hidden="true">↗</span></RouterLink></div></article></template>
