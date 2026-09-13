<script setup>
import { computed, onMounted, ref } from 'vue'
import { get } from '../api/client'
import ItemGrid from './ItemGrid.vue'
import StateMessage from './StateMessage.vue'
import { useI18n } from '../i18n'

defineProps({ embedded: Boolean })
const data = ref(null)
const loading = ref(true)
const error = ref(null)
const { t, categoryLabel, errorKey } = useI18n()
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')

function categoryRoute(category) {
  const routes = { BOOK: '/books', MOVIE: '/movies', GAME: '/games', PROJECT: '/projects', JOURNAL: '/journal' }
  return category.is_root ? (routes[category.code] || '/journal') : '/log'
}

onMounted(async () => {
  try {
    data.value = await get('/api/public/index')
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="reference-index" :class="{ 'embedded-index': embedded }" aria-labelledby="reference-index-title">
    <div class="section-heading">
      <div class="eyebrow mono">{{ t('index.eyebrow') }}</div>
      <component :is="embedded ? 'h2' : 'h1'" id="reference-index-title">{{ t(embedded ? 'index.embeddedTitle' : 'index.title') }}</component>
      <p v-if="!embedded" class="muted">{{ t('index.description') }}</p>
    </div>

    <StateMessage v-if="loading" type="loading" :message="t('state.buildingIndex')" />
    <StateMessage v-else-if="error" type="error" :message="localizedError" />
    <template v-else>
      <div class="index-columns">
        <div>
          <h2 class="subheading">{{ t('index.categories') }}</h2>
          <RouterLink
            v-for="category in data.categories"
            :key="category.id"
            class="index-row"
            :to="categoryRoute(category)"
          >
            <span class="index-name">{{ category.is_root ? categoryLabel(category.code, category.name) : category.name }}</span>
            <span class="mono">{{ String(category.note_count).padStart(2, '0') }} <span aria-hidden="true">↗</span></span>
          </RouterLink>
        </div>

        <div>
          <h2 class="subheading">{{ t('index.tags') }}</h2>
          <div v-if="data.tags.length" class="index-tags"><RouterLink v-for="tag in data.tags" :key="tag.id" class="index-tag" :to="`/tag/${tag.slug}`">
            <span>#{{ tag.name }}</span>
            <span class="mono">{{ tag.note_count }}</span>
          </RouterLink></div>
          <p v-else class="field-help">{{ t('state.noTags') }}</p>
        </div>
      </div>

      <template v-if="!embedded"><h2 class="subheading">{{ t('index.publicItems') }}</h2><ItemGrid :items="data.items" /></template>
    </template>
  </section>
</template>
