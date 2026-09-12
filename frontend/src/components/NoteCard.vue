<script setup>
import { inject } from 'vue'
import { useI18n } from '../i18n'
defineProps({ note: { type: Object, required: true } })
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t } = useI18n()
function formatDate(value) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return d(value, { dateStyle: 'medium', timeStyle: 'short' }, timeZone) }
</script>
<template><article class="note-card"><div class="note-rail"><span class="rail-tick"></span><time class="timestamp mono" :datetime="note.started_at">{{ formatDate(note.started_at) }}</time></div><div class="note-body"><div class="note-kicker mono"><span>{{ note.archive_label }}</span><span v-for="item in note.items" :key="`i${item.id}`" class="chip chip-item">{{ item.title }}</span><RouterLink v-for="tag in note.tags" :key="`t${tag.id}`" class="chip" :to="`/tag/${tag.slug}`">#{{ tag.name }}</RouterLink></div><h3><RouterLink :to="`/n/${note.id}`">{{ note.title || t('common.untitledEvent') }}</RouterLink></h3><div class="note-excerpt sanitized-content" v-if="note.content_html_sanitized" v-html="note.content_html_sanitized"></div><RouterLink class="permalink" :to="`/n/${note.id}`">{{ t('common.openNote') }} <span aria-hidden="true">↗</span></RouterLink></div></article></template>
