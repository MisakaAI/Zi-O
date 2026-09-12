<script setup>
import { onMounted, ref } from 'vue'
import { get } from '../api/client'
import ItemGrid from '../components/ItemGrid.vue'
import StateMessage from '../components/StateMessage.vue'
const data = ref(null); const loading = ref(true); const error = ref('')
onMounted(async () => { try { data.value = await get('/api/public/index') } catch (err) { error.value = err.message } finally { loading.value = false } })
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">REFERENCE / INDEX</div><h1>Everything has a place.</h1></div><StateMessage v-if="loading" type="loading" message="Building index…" /><StateMessage v-else-if="error" type="error" :message="error" /><template v-else><div class="index-columns"><div><h2 class="subheading">Categories</h2><RouterLink v-for="category in data.categories" :key="category.id" class="index-row" :to="category.is_root ? `/${category.code === 'BOOK' ? 'books' : category.code === 'MOVIE' ? 'movies' : category.code === 'GAME' ? 'games' : category.code === 'CODE' ? 'code' : 'journal'}` : '/log'"><span>{{ category.name }}</span><span class="mono">{{ category.note_count }}</span></RouterLink></div><div><h2 class="subheading">Tags</h2><RouterLink v-for="tag in data.tags" :key="tag.id" class="index-row" :to="`/tag/${tag.slug}`"><span>#{{ tag.name }}</span><span class="mono">{{ tag.note_count }}</span></RouterLink></div></div><h2 class="subheading">Public items</h2><ItemGrid :items="data.items" /></template></section></template>

