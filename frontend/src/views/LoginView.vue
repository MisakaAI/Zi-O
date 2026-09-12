<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { post } from '../api/client'
import { useI18n } from '../i18n'
const username = ref('misaka'); const password = ref(''); const error = ref(null); const busy = ref(false); const router = useRouter()
const { t, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
async function submit() { busy.value = true; error.value = null; try { await post('/api/auth/login', { username: username.value, password: password.value }); router.push('/manage') } catch (err) { error.value = err } finally { busy.value = false } }
</script>
<template><section class="auth-card"><div class="eyebrow mono">{{ t('login.eyebrow') }}</div><h1>{{ t('login.title') }}</h1><form @submit.prevent="submit"><label>{{ t('login.username') }}<input v-model="username" autocomplete="username" required></label><label>{{ t('login.password') }}<input v-model="password" type="password" autocomplete="current-password" required></label><p v-if="error" class="inline-error" role="alert">{{ localizedError }}</p><button class="primary-button" :disabled="busy">{{ busy ? t('login.checking') : t('login.enterArchive') }}</button></form></section></template>
