<script setup>
import NoteCard from './NoteCard.vue'
import StateMessage from './StateMessage.vue'
import { useI18n } from '../i18n'
defineProps({ notes: { type: Array, default: () => [] }, loading: Boolean, error: String, nextCursor: String })
const emit = defineEmits(['load-more'])
const { t } = useI18n()
</script>
<template><StateMessage v-if="loading && !notes.length" type="loading" :message="t('state.readingArchive')" /><StateMessage v-else-if="error" type="error" :message="error" /><StateMessage v-else-if="!notes.length" type="empty" :message="t('state.noPublicEventsHere')" /><div v-else class="timeline" aria-live="polite"><NoteCard v-for="note in notes" :key="note.id" :note="note" /><button v-if="nextCursor" class="load-more" :disabled="loading" @click="emit('load-more')">{{ loading ? t('state.loading') : t('common.loadOlder') }}</button></div></template>
