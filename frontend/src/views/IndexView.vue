<script setup>
import { computed, onMounted, ref } from 'vue'
import { get } from '../api/client'
import ItemGrid from '../components/ItemGrid.vue'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'
const data = ref(null); const loading = ref(true); const error = ref(null)
const { t, categoryLabel, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
onMounted(async () => { try { data.value = await get('/api/public/index') } catch (err) { error.value = err } finally { loading.value = false } })
</script>
<template><section><div class="section-heading"><div class="eyebrow mono">{{ t('index.eyebrow') }}</div><h1>{{ t('index.title') }}</h1></div><StateMessage v-if="loading" type="loading" :message="t('state.buildingIndex')" /><StateMessage v-else-if="error" type="error" :message="localizedError" /><template v-else><div class="index-columns"><div><h2 class="subheading">{{ t('index.categories') }}</h2><RouterLink v-for="category in data.categories" :key="category.id" class="index-row" :to="category.is_root ? `/${category.code === 'BOOK' ? 'books' : category.code === 'MOVIE' ? 'movies' : category.code === 'GAME' ? 'games' : category.code === 'CODE' ? 'code' : 'journal'}` : '/log'"><span>{{ category.is_root ? categoryLabel(category.code, category.name) : category.name }}</span><span class="mono">{{ category.note_count }}</span></RouterLink></div><div><h2 class="subheading">{{ t('index.tags') }}</h2><RouterLink v-for="tag in data.tags" :key="tag.id" class="index-row" :to="`/tag/${tag.slug}`"><span>#{{ tag.name }}</span><span class="mono">{{ tag.note_count }}</span></RouterLink></div></div><h2 class="subheading">{{ t('index.publicItems') }}</h2><ItemGrid :items="data.items" /></template></section></template>
