<script setup>
import NoteCard from './NoteCard.vue'
import StateMessage from './StateMessage.vue'
defineProps({ notes: { type: Array, default: () => [] }, loading: Boolean, error: String, nextCursor: String })
const emit = defineEmits(['load-more'])
</script>
<template><StateMessage v-if="loading && !notes.length" type="loading" message="Reading the archive…" /><StateMessage v-else-if="error" type="error" :message="error" /><StateMessage v-else-if="!notes.length" type="empty" message="No public events here yet." /><div v-else class="timeline" aria-live="polite"><NoteCard v-for="note in notes" :key="note.id" :note="note" /><button v-if="nextCursor" class="load-more" :disabled="loading" @click="emit('load-more')">{{ loading ? 'LOADING…' : 'LOAD OLDER' }}</button></div></template>

