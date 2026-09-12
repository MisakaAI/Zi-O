<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { post } from '../api/client'
const username = ref('misaka'); const password = ref(''); const error = ref(''); const busy = ref(false); const router = useRouter()
async function submit() { busy.value = true; error.value = ''; try { await post('/api/auth/login', { username: username.value, password: password.value }); router.push('/manage') } catch (err) { error.value = err.message } finally { busy.value = false } }
</script>
<template><section class="auth-card"><div class="eyebrow mono">MANAGE / AUTH</div><h1>Sign in</h1><form @submit.prevent="submit"><label>Username<input v-model="username" autocomplete="username" required></label><label>Password<input v-model="password" type="password" autocomplete="current-password" required></label><p v-if="error" class="inline-error" role="alert">{{ error }}</p><button class="primary-button" :disabled="busy">{{ busy ? 'CHECKING…' : 'ENTER ARCHIVE' }}</button></form></section></template>

