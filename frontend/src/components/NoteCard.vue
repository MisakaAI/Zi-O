<script setup>
import { computed, inject } from 'vue'
import { useI18n } from '../i18n'
const props = defineProps({ note: { type: Object, required: true } })
const siteTimezone = inject('siteTimezone', 'UTC')
const { d, t } = useI18n()
function formatDate(value, options) { const timeZone = typeof siteTimezone === 'string' ? siteTimezone : siteTimezone.value; return d(value, options, timeZone) }
// 列表只显示纯文本摘要，避免正文标题打乱页面层级，或长内容截断可聚焦链接。
const excerpt = computed(() => {
  const document = new DOMParser().parseFromString(props.note.content_html_sanitized || '', 'text/html')
  document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, pre, blockquote, br').forEach(node => node.append(' '))
  return (document.body.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 320)
})
</script>
<template>
  <article class="note-card">
    <div class="note-rail"><span class="rail-tick" aria-hidden="true"></span><time class="timestamp note-time mono" :datetime="note.started_at"><span>{{ formatDate(note.started_at, { year: 'numeric', month: 'short', day: 'numeric' }) }}</span><span>{{ formatDate(note.started_at, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) }}</span></time></div>
    <div class="note-body">
      <RouterLink class="note-kicker mono" :to="`/n/${note.id}`">{{ note.archive_label }}</RouterLink>
      <h3><RouterLink :to="`/n/${note.id}`">{{ note.title || t('common.untitledEvent') }}</RouterLink></h3>
      <p v-if="excerpt" class="note-excerpt">{{ excerpt }}</p>
      <div v-if="note.items?.length || note.tags?.length" class="chip-row">
        <RouterLink v-for="item in note.items" :key="`i${item.id}`" class="chip chip-item" :to="`/items/${item.id}`">{{ item.title }}</RouterLink>
        <RouterLink v-for="tag in note.tags" :key="`t${tag.id}`" class="chip chip-tag" :to="`/tag/${tag.slug}`">#{{ tag.name }}</RouterLink>
      </div>
      <RouterLink class="permalink" :to="`/n/${note.id}`">{{ t('common.openNote') }} <span aria-hidden="true">↗</span></RouterLink>
    </div>
  </article>
</template>
