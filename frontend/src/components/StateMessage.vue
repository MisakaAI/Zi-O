<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n'

const props = defineProps({ type: { type: String, default: 'empty' }, message: { type: String, default: '' } })
const { t } = useI18n()
const defaultMessage = computed(() => t({ loading: 'state.loading', error: 'state.error', empty: 'state.empty' }[props.type] || 'state.empty'))
</script>
<template><div class="state-message" :class="`state-${type}`" :role="type === 'error' ? 'alert' : 'status'"><span class="state-mark" aria-hidden="true">{{ type === 'error' ? '!' : type === 'loading' ? '…' : '—' }}</span><span>{{ message || defaultMessage }}</span></div></template>
