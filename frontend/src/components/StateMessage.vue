<script setup>
defineProps({ type: { type: String, default: 'empty' }, message: { type: String, default: '' } })
</script>
<template><div class="state-message" :class="`state-${type}`" role="status"><span class="state-mark" aria-hidden="true">{{ type === 'error' ? '!' : type === 'loading' ? '…' : '—' }}</span><span>{{ message || (type === 'loading' ? 'Loading…' : type === 'error' ? 'Unable to load this slice.' : 'No records in this slice yet.') }}</span></div></template>

