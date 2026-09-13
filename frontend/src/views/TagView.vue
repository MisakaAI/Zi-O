<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api/client'
import TimelineList from '../components/TimelineList.vue'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'

const route = useRoute()
const data = ref(null)
const availableTags = ref([])
const loading = ref(true)
const error = ref(null)
const loadingMore = ref(false)
const moreError = ref(null)
const { t, errorKey } = useI18n()
const localizedMoreError = computed(() => moreError.value ? t(errorKey(moreError.value)) : '')
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')

function selectedSlugs() {
  const extra = Array.isArray(route.query.tag) ? route.query.tag : route.query.tag ? [route.query.tag] : []
  return [...new Set([route.params.slug, ...extra].filter(Boolean))]
}

function apiPath(cursor = null) {
  const slugs = selectedSlugs()
  const params = new URLSearchParams()
  slugs.slice(1).forEach(slug => params.append('tag', slug))
  if (cursor) params.set('cursor', cursor)
  const query = params.toString()
  return `/api/public/tags/${encodeURIComponent(slugs[0])}${query ? `?${query}` : ''}`
}

function tagDestination(slug) {
  const current = selectedSlugs()
  const next = current.includes(slug) ? current.filter(value => value !== slug) : [...current, slug]
  if (!next.length) return '/log'
  const params = new URLSearchParams()
  next.slice(1).forEach(value => params.append('tag', value))
  const query = params.toString()
  return `/tag/${encodeURIComponent(next[0])}${query ? `?${query}` : ''}`
}

async function load() {
  const requestPath = route.fullPath
  data.value = null
  loading.value = true
  error.value = null
  try {
    const requests = [get(apiPath())]
    if (!availableTags.value.length) requests.push(get('/api/public/index'))
    const [result, index] = await Promise.all(requests)
    if (route.fullPath !== requestPath) return
    data.value = result
    if (index) availableTags.value = index.tags
  } catch (err) {
    if (route.fullPath === requestPath) error.value = err
  } finally {
    if (route.fullPath === requestPath) loading.value = false
  }
}

async function loadMore() {
  if (!data.value?.next_cursor || loadingMore.value) return
  loadingMore.value = true
  moreError.value = null
  try {
    const next = await get(apiPath(data.value.next_cursor))
    data.value.items.push(...next.items)
    data.value.next_cursor = next.next_cursor
  } catch (err) {
    moreError.value = err
  } finally {
    loadingMore.value = false
  }
}

watch(() => route.fullPath, load, { immediate: true })
</script>

<template>
  <section>
    <StateMessage v-if="loading" type="loading" :message="t('state.readingTag')" />
    <StateMessage v-else-if="error" type="error" :message="localizedError" />
    <template v-else>
      <div class="section-heading">
        <div class="eyebrow mono">{{ t('tag.eyebrow', { slug: data.tags.map(tag => tag.slug).join(' + ') }) }}</div>
        <h1>{{ data.tags.map(tag => `#${tag.name}`).join(' + ') }}</h1>
        <p>{{ t('tag.filterHint') }}</p>
      </div>
      <nav class="tag-filters" :aria-label="t('tag.filterLabel')">
        <RouterLink
          v-for="tag in availableTags"
          :key="tag.id"
          class="tag-filter"
          :class="{ active: selectedSlugs().includes(tag.slug) }"
          :aria-current="selectedSlugs().includes(tag.slug) ? 'true' : undefined"
          :to="tagDestination(tag.slug)"
        ><span aria-hidden="true">{{ selectedSlugs().includes(tag.slug) ? '✓' : '+' }}</span>#{{ tag.name }} <small>{{ tag.note_count }}</small></RouterLink>
      </nav>
      <TimelineList
        :notes="data.items"
        :next-cursor="data.next_cursor"
        :loading="loadingMore"
        :error="localizedMoreError"
        @load-more="loadMore"
      />
    </template>
  </section>
</template>
