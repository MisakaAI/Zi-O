<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get, patch, post, remove } from '../api/client'
import StateMessage from '../components/StateMessage.vue'
import { useI18n } from '../i18n'

const section = ref('notes')
const notes = ref([]); const noteCursor = ref(null); const notesLoading = ref(false); const items = ref([]); const categories = ref([]); const tags = ref([]); const settings = ref(null)
const loading = ref(true); const error = ref(null); const message = ref(null)
const editingNoteId = ref(null); const editingItemId = ref(null); const posterFile = ref(null)
const blankNote = () => ({ title: '', content_raw: '', content_format: 'markdown', started_at: localInput(new Date()), ended_at: '', visibility: 'private', static_path: '', category_id: '', secondary_categories: [], item_ids: [], item_links: {}, tag_ids: [] })
const noteForm = ref(blankNote())
const blankItem = () => ({ category_id: '', title: '', subtitle: '', creator: '', visibility: 'private', metadata_json_text: '{}' })
const itemForm = ref(blankItem())
const tagName = ref(''); const categoryName = ref(''); const categoryParent = ref('')
const { t, categoryLabel, errorKey } = useI18n()
const tabs = computed(() => [
  { name: 'notes', label: t('manage.tabs.notes') },
  { name: 'items', label: t('manage.tabs.items') },
  { name: 'taxonomy', label: t('manage.tabs.taxonomy') },
  { name: 'settings', label: t('manage.tabs.settings') },
])
const roots = computed(() => categories.value.filter(c => c.is_root))
const selectedItems = computed(() => noteForm.value.item_ids.map(id => items.value.find(item => item.id === Number(id))).filter(Boolean))
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
const localizedMessage = computed(() => message.value ? t(message.value.key, message.value.params) : '')
function displayCategory(category) { return category.is_root ? categoryLabel(category.code, category.name) : category.name }
function setMessage(key, params) { message.value = { key, params } }

watch(() => noteForm.value.item_ids, ids => {
  for (const id of ids) {
    if (!noteForm.value.item_links[id]) noteForm.value.item_links[id] = { context_label: '', progress_text: '' }
  }
}, { deep: true })

async function load() {
  loading.value = true; error.value = null
  try {
    const [n, i, c, t, s] = await Promise.all([get('/api/manage/notes'), get('/api/manage/items'), get('/api/manage/categories'), get('/api/manage/tags'), get('/api/manage/settings')])
    notes.value = n.items; noteCursor.value = n.next_cursor; items.value = i.items; categories.value = c.items; tags.value = t.items; settings.value = s
    if (!noteForm.value.category_id) noteForm.value.category_id = roots.value.find(c => c.code === 'JOURNAL')?.id || roots.value[0]?.id
    if (!itemForm.value.category_id) itemForm.value.category_id = roots.value[0]?.id
    if (!categoryParent.value) categoryParent.value = roots.value[0]?.id
  } catch (err) { error.value = err } finally { loading.value = false }
}
function localInput(value) { if (!value) return ''; const date = new Date(value); const pad = n => String(n).padStart(2, '0'); return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}` }
function resetNote() { editingNoteId.value = null; noteForm.value = blankNote(); if (roots.value.length) noteForm.value.category_id = roots.value.find(c => c.code === 'JOURNAL')?.id || roots.value[0].id }
function editNote(note) { editingNoteId.value = note.id; noteForm.value = { ...blankNote(), title: note.title, content_raw: note.content_raw, content_format: note.content_format, started_at: localInput(note.started_at), ended_at: localInput(note.ended_at), visibility: note.visibility, static_path: note.static_path || '', category_id: note.categories.find(c => c.is_primary)?.id || roots.value[0]?.id, secondary_categories: note.categories.filter(c => !c.is_primary).map(c => c.id), item_ids: note.items.map(item => item.id), item_links: Object.fromEntries(note.items.map(item => [item.id, { context_label: item.context_label || '', progress_text: item.progress_text || '' }])), tag_ids: note.tags.map(tag => tag.id) } }
async function loadOlderNotes() {
  if (!noteCursor.value || notesLoading.value) return
  notesLoading.value = true; error.value = null
  try {
    const data = await get(`/api/manage/notes?cursor=${encodeURIComponent(noteCursor.value)}`)
    notes.value.push(...data.items); noteCursor.value = data.next_cursor
  } catch (err) { error.value = err } finally { notesLoading.value = false }
}
async function saveNote() {
  error.value = null
  try {
    const categoryIds = [Number(noteForm.value.category_id), ...noteForm.value.secondary_categories.map(Number)].filter(Boolean)
    const payload = { title: noteForm.value.title, content_raw: noteForm.value.content_raw, content_format: noteForm.value.content_format, started_at: new Date(noteForm.value.started_at).toISOString(), ended_at: noteForm.value.ended_at ? new Date(noteForm.value.ended_at).toISOString() : null, visibility: noteForm.value.visibility, static_path: noteForm.value.static_path || null, categories: categoryIds.map((id, index) => ({ category_id: id, is_primary: index === 0 })), items: noteForm.value.item_ids.map(id => ({ item_id: Number(id), context_label: noteForm.value.item_links[id]?.context_label || null, progress_text: noteForm.value.item_links[id]?.progress_text || null })), tag_ids: noteForm.value.tag_ids.map(Number) }
    if (editingNoteId.value) await patch(`/api/manage/notes/${editingNoteId.value}`, payload); else await post('/api/manage/notes', payload)
    setMessage(editingNoteId.value ? 'manage.messages.noteUpdated' : 'manage.messages.noteCreated'); resetNote(); await load()
  } catch (err) { error.value = err }
}
async function deleteNote(id) { if (!window.confirm(t('manage.prompts.deleteNote'))) return; try { await remove(`/api/manage/notes/${id}`); setMessage('manage.messages.noteDeleted'); await load() } catch (err) { error.value = err } }

function editItem(item) { editingItemId.value = item.id; itemForm.value = { category_id: item.category_id, title: item.title, subtitle: item.subtitle, creator: item.creator, visibility: item.visibility, metadata_json_text: JSON.stringify(item.metadata_json || {}, null, 2) } }
function resetItem() { editingItemId.value = null; itemForm.value = blankItem(); if (roots.value.length) itemForm.value.category_id = roots.value[0].id; posterFile.value = null }
async function saveItem() {
  try {
    let metadata_json
    try { metadata_json = JSON.parse(itemForm.value.metadata_json_text || '{}') } catch { const metadataError = new Error(t('manage.errors.metadataInvalid')); metadataError.code = 'invalid_metadata'; throw metadataError }
    const payload = { category_id: Number(itemForm.value.category_id), title: itemForm.value.title, subtitle: itemForm.value.subtitle, creator: itemForm.value.creator, metadata_json }
    const result = editingItemId.value ? await patch(`/api/manage/items/${editingItemId.value}`, payload) : await post('/api/manage/items', { ...payload, visibility: itemForm.value.visibility })
    if (editingItemId.value && result.visibility !== itemForm.value.visibility) await post(`/api/manage/items/${result.id}/visibility`, { visibility: itemForm.value.visibility })
    if (posterFile.value) { const response = await fetch(`/api/manage/items/${result.id}/poster`, { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': posterFile.value.type }, body: posterFile.value }); if (!response.ok) { const uploadError = new Error(t('manage.errors.posterUploadFailed')); uploadError.code = 'poster_upload_failed'; throw uploadError } }
    setMessage(editingItemId.value ? 'manage.messages.itemUpdated' : 'manage.messages.itemCreated'); resetItem(); await load()
  } catch (err) { error.value = err }
}
async function deleteItem(id) { if (!window.confirm(t('manage.prompts.deleteItem'))) return; try { await remove(`/api/manage/items/${id}`); setMessage('manage.messages.itemDeleted'); await load() } catch (err) { error.value = err } }
async function toggleItem(item) { try { await post(`/api/manage/items/${item.id}/visibility`, { visibility: item.visibility === 'public' ? 'private' : 'public' }); await load() } catch (err) { error.value = err } }
async function publishItemNotes(item) { try { const result = await post(`/api/manage/items/${item.id}/notes/set-public`, {}); setMessage('manage.publishedNotes', { updated: result.updated_count, blocked: result.blocked_count }); await load() } catch (err) { error.value = err } }
async function createTag() { try { await post('/api/manage/tags', { name: tagName.value }); tagName.value = ''; await load() } catch (err) { error.value = err } }
async function editTag(tag) { const name = window.prompt(t('manage.prompts.tagName'), tag.name); if (name && name !== tag.name) { try { await patch(`/api/manage/tags/${tag.id}`, { name }); await load() } catch (err) { error.value = err } } }
async function deleteTag(id) { if (window.confirm(t('manage.prompts.deleteTag'))) { try { await remove(`/api/manage/tags/${id}`); await load() } catch (err) { error.value = err } } }
async function createCategory() { try { await post('/api/manage/categories', { name: categoryName.value, parent_id: Number(categoryParent.value) }); categoryName.value = ''; await load() } catch (err) { error.value = err } }
async function editCategory(category) { const name = window.prompt(t('manage.prompts.categoryName'), category.name); if (name && name !== category.name) { try { await patch(`/api/manage/categories/${category.id}`, { name }); await load() } catch (err) { error.value = err } } }
async function deleteCategory(id) { if (window.confirm(t('manage.prompts.deleteCategory'))) { try { await remove(`/api/manage/categories/${id}`); await load() } catch (err) { error.value = err } } }
async function saveSettings() { try { await patch('/api/manage/settings', settings.value); setMessage('manage.messages.settingsSaved') } catch (err) { error.value = err } }
onMounted(load)
</script>

<template>
  <section class="manage-page">
    <div class="section-heading">
      <div class="eyebrow mono">{{ t('manage.eyebrow') }}</div>
      <h1>{{ t('manage.title') }}</h1>
      <p class="muted">{{ t('manage.description') }}</p>
    </div>
    <StateMessage v-if="loading" type="loading" :message="t('manage.opening')" />
    <p v-if="error" class="inline-error" role="alert">{{ localizedError }}</p>
    <p v-if="message" class="success-message" role="status">{{ localizedMessage }}</p>
    <template v-if="!loading && settings">
      <div class="manage-tabs">
        <button v-for="tab in tabs" :key="tab.name" :class="{ active: section === tab.name }" @click="section = tab.name">{{ tab.label }}</button>
      </div>

      <div v-if="section === 'notes'" class="manage-grid">
        <form class="editor-card" @submit.prevent="saveNote">
          <h2>{{ editingNoteId ? t('manage.editNote') : t('manage.newNote') }}</h2>
          <label>{{ t('manage.fields.title') }}<input v-model="noteForm.title" maxlength="200"></label>
          <label>{{ t('manage.fields.startedAt') }}<input v-model="noteForm.started_at" type="datetime-local" required></label>
          <label>{{ t('manage.fields.endedAt') }}<input v-model="noteForm.ended_at" type="datetime-local"></label>
          <label>{{ t('manage.fields.primaryCategory') }}<select v-model="noteForm.category_id" required><option v-for="category in categories" :key="category.id" :value="category.id">{{ displayCategory(category) }}</option></select></label>
          <label>{{ t('manage.fields.secondaryCategories') }}<select v-model="noteForm.secondary_categories" multiple><option v-for="category in categories" :key="category.id" :value="category.id">{{ displayCategory(category) }}</option></select></label>
          <label>{{ t('manage.fields.items') }}<select v-model="noteForm.item_ids" multiple><option v-for="item in items" :key="item.id" :value="item.id">{{ item.title }}</option></select></label>
          <fieldset v-for="item in selectedItems" :key="item.id" class="item-link-fields">
            <legend>{{ item.title }}</legend>
            <label>{{ t('manage.fields.itemContext') }}<input v-model="noteForm.item_links[item.id].context_label" maxlength="200"></label>
            <label>{{ t('manage.fields.progress') }}<input v-model="noteForm.item_links[item.id].progress_text" maxlength="200"></label>
          </fieldset>
          <label>{{ t('manage.fields.tags') }}<select v-model="noteForm.tag_ids" multiple><option v-for="tag in tags" :key="tag.id" :value="tag.id">#{{ tag.name }}</option></select></label>
          <label>{{ t('manage.fields.staticHtmlPath') }}<input v-model="noteForm.static_path" placeholder="pages/example.html"></label>
          <label>{{ t('manage.fields.format') }}<select v-model="noteForm.content_format"><option value="markdown">{{ t('common.markdown') }}</option><option value="html">{{ t('common.html') }}</option></select></label>
          <label>{{ t('manage.fields.visibility') }}<select v-model="noteForm.visibility"><option value="private">{{ t('common.private') }}</option><option value="public">{{ t('common.public') }}</option></select></label>
          <label>{{ t('manage.fields.content') }}<textarea v-model="noteForm.content_raw" rows="10"></textarea></label>
          <div class="button-row"><button class="primary-button">{{ editingNoteId ? t('manage.buttons.updateNote') : t('manage.buttons.saveNote') }}</button><button v-if="editingNoteId" type="button" class="link-button" @click="resetNote">{{ t('common.cancel') }}</button></div>
        </form>
        <div>
          <h2>{{ t('manage.notes') }}</h2>
          <div v-for="note in notes" :key="note.id" class="admin-row">
            <span class="mono">{{ note.archive_label }}</span>
            <span>{{ note.title || t('common.untitledEvent') }}</span>
            <span class="muted">{{ t(`common.${note.visibility}`) }}</span>
            <button class="link-button" @click="editNote(note)">{{ t('common.edit') }}</button>
            <button class="danger-button" @click="deleteNote(note.id)">{{ t('common.delete') }}</button>
          </div>
          <button v-if="noteCursor" class="load-more" :disabled="notesLoading" @click="loadOlderNotes">{{ notesLoading ? t('state.loading') : t('common.loadOlderNotes') }}</button>
        </div>
      </div>

      <div v-else-if="section === 'items'" class="manage-grid">
        <form class="editor-card" @submit.prevent="saveItem">
          <h2>{{ editingItemId ? t('manage.editItem') : t('manage.newItem') }}</h2>
          <label>{{ t('manage.fields.category') }}<select v-model="itemForm.category_id" required><option v-for="root in roots" :key="root.id" :value="root.id">{{ displayCategory(root) }}</option></select></label>
          <label>{{ t('manage.fields.title') }}<input v-model="itemForm.title" required maxlength="200"></label>
          <label>{{ t('manage.fields.subtitle') }}<input v-model="itemForm.subtitle"></label>
          <label>{{ t('manage.fields.creator') }}<input v-model="itemForm.creator"></label>
          <label>{{ t('manage.fields.visibility') }}<select v-model="itemForm.visibility"><option value="private">{{ t('common.private') }}</option><option value="public">{{ t('common.public') }}</option></select></label>
          <label>{{ t('manage.fields.metadataJson') }}<textarea v-model="itemForm.metadata_json_text" rows="6" spellcheck="false"></textarea></label>
          <label>{{ t('manage.fields.poster') }}<input type="file" accept="image/jpeg,image/png,image/webp" @change="posterFile = $event.target.files[0] || null"></label>
          <div class="button-row"><button class="primary-button">{{ editingItemId ? t('manage.buttons.updateItem') : t('manage.buttons.saveItem') }}</button><button v-if="editingItemId" type="button" class="link-button" @click="resetItem">{{ t('common.cancel') }}</button></div>
        </form>
        <div>
          <h2>{{ t('manage.items') }}</h2>
          <div v-for="item in items" :key="item.id" class="admin-row">
            <span>{{ item.title }}</span>
            <span class="muted">{{ t(`common.${item.visibility}`) }}<small v-if="item.private_note_count">{{ t('manage.privateNotes', { count: item.private_note_count }) }}</small></span>
            <button class="link-button" @click="toggleItem(item)">{{ item.visibility === 'public' ? t('manage.buttons.makePrivate') : t('manage.buttons.publish') }}</button>
            <button v-if="item.visibility === 'public' && item.private_note_count" class="link-button" @click="publishItemNotes(item)">{{ t('manage.buttons.publishNotes') }}</button>
            <button class="link-button" @click="editItem(item)">{{ t('common.edit') }}</button>
            <button class="danger-button" @click="deleteItem(item.id)">{{ t('common.delete') }}</button>
          </div>
        </div>
      </div>

      <div v-else-if="section === 'taxonomy'" class="manage-grid">
        <div class="editor-card">
          <h2>{{ t('manage.newTag') }}</h2>
          <form @submit.prevent="createTag"><label>{{ t('manage.fields.name') }}<input v-model="tagName" required></label><button class="primary-button">{{ t('manage.buttons.addTag') }}</button></form>
          <h2>{{ t('manage.newChildCategory') }}</h2>
          <form @submit.prevent="createCategory"><label>{{ t('manage.fields.root') }}<select v-model="categoryParent" required><option v-for="root in roots" :key="root.id" :value="root.id">{{ displayCategory(root) }}</option></select></label><label>{{ t('manage.fields.name') }}<input v-model="categoryName" required></label><button class="primary-button">{{ t('manage.buttons.addCategory') }}</button></form>
        </div>
        <div>
          <h2>{{ t('manage.tags') }}</h2>
          <div v-for="tag in tags" :key="tag.id" class="admin-row"><span>#{{ tag.name }}</span><span class="mono">{{ tag.slug }}</span><button class="link-button" @click="editTag(tag)">{{ t('common.edit') }}</button><button class="danger-button" @click="deleteTag(tag.id)">{{ t('common.delete') }}</button></div>
          <h2>{{ t('manage.categories') }}</h2>
          <div v-for="category in categories" :key="category.id" class="admin-row"><span>{{ displayCategory(category) }}</span><span class="mono">{{ category.code }}</span><template v-if="!category.is_root"><button class="link-button" @click="editCategory(category)">{{ t('common.edit') }}</button><button class="danger-button" @click="deleteCategory(category.id)">{{ t('common.delete') }}</button></template></div>
        </div>
      </div>

      <form v-else class="editor-card settings-form" @submit.prevent="saveSettings">
        <h2>{{ t('manage.siteSettings') }}</h2>
        <label>{{ t('manage.fields.siteTitle') }}<input v-model="settings.site_title"></label>
        <label>{{ t('manage.fields.tagline') }}<input v-model="settings.site_tagline"></label>
        <label>{{ t('manage.fields.timezone') }}<input v-model="settings.timezone"></label>
        <label>{{ t('manage.fields.nowStatus') }}<input v-model="settings.now_status"></label>
        <label>{{ t('manage.fields.aboutFormat') }}<select v-model="settings.about_format"><option value="markdown">{{ t('common.markdown') }}</option><option value="html">{{ t('common.html') }}</option></select></label>
        <label>{{ t('manage.fields.about') }}<textarea v-model="settings.about_raw" rows="10"></textarea></label>
        <label>{{ t('manage.fields.currentNoteId') }}<input v-model.number="settings.current_note_id" type="number" min="1"></label>
        <button class="primary-button">{{ t('manage.buttons.saveSettings') }}</button>
      </form>
    </template>
  </section>
</template>
