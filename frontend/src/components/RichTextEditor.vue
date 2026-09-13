<script setup>
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import Image from '@tiptap/extension-image'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { api } from '../api/client'
import { useI18n } from '../i18n'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { t, errorKey } = useI18n()
const labelId = `rich-text-${useId()}`
const imageInput = ref(null)
const sourceMode = ref(false)
const uploading = ref(false)
const uploadError = ref(null)
const localizedUploadError = computed(() => uploadError.value ? t(errorKey(uploadError.value)) : '')

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  extensions: [
    StarterKit.configure({ heading: { levels: [2, 3] } }),
    Image.configure({ allowBase64: false }),
  ],
  editorProps: {
    attributes: {
      class: 'sanitized-content rich-text-surface',
      'aria-labelledby': labelId,
    },
  },
  onUpdate: ({ editor: currentEditor }) => emit('update:modelValue', currentEditor.getHTML()),
})

watch(() => props.modelValue, value => {
  if (!editor.value || editor.value.getHTML() === value) return
  editor.value.commands.setContent(value || '', { emitUpdate: false })
})
watch(() => props.disabled, value => editor.value?.setEditable(!value))
onBeforeUnmount(() => editor.value?.destroy())

const controls = [
  { key: 'paragraph', text: '¶', command: () => editor.value.chain().focus().setParagraph().run(), active: () => editor.value.isActive('paragraph') },
  { key: 'heading2', text: 'H2', command: () => editor.value.chain().focus().toggleHeading({ level: 2 }).run(), active: () => editor.value.isActive('heading', { level: 2 }) },
  { key: 'heading3', text: 'H3', command: () => editor.value.chain().focus().toggleHeading({ level: 3 }).run(), active: () => editor.value.isActive('heading', { level: 3 }) },
  { key: 'bold', text: 'B', command: () => editor.value.chain().focus().toggleBold().run(), active: () => editor.value.isActive('bold') },
  { key: 'italic', text: 'I', command: () => editor.value.chain().focus().toggleItalic().run(), active: () => editor.value.isActive('italic') },
  { key: 'strike', text: 'S', command: () => editor.value.chain().focus().toggleStrike().run(), active: () => editor.value.isActive('strike') },
  { key: 'inlineCode', text: '<>', command: () => editor.value.chain().focus().toggleCode().run(), active: () => editor.value.isActive('code') },
  { key: 'bulletList', text: '•', command: () => editor.value.chain().focus().toggleBulletList().run(), active: () => editor.value.isActive('bulletList') },
  { key: 'orderedList', text: '1.', command: () => editor.value.chain().focus().toggleOrderedList().run(), active: () => editor.value.isActive('orderedList') },
  { key: 'quote', text: '“”', command: () => editor.value.chain().focus().toggleBlockquote().run(), active: () => editor.value.isActive('blockquote') },
  { key: 'codeBlock', text: '{ }', command: () => editor.value.chain().focus().toggleCodeBlock().run(), active: () => editor.value.isActive('codeBlock') },
  { key: 'horizontalRule', text: '—', command: () => editor.value.chain().focus().setHorizontalRule().run(), active: () => false },
]

function toggleSourceMode() {
  if (sourceMode.value && editor.value) editor.value.commands.setContent(props.modelValue || '', { emitUpdate: false })
  sourceMode.value = !sourceMode.value
}

function escapeAttribute(value) {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

async function uploadImage(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  uploadError.value = null
  try {
    const result = await api('/api/manage/content-images', {
      method: 'POST',
      headers: { 'Content-Type': file.type },
      body: file,
    })
    const alt = file.name.slice(0, 200)
    if (sourceMode.value) {
      emit('update:modelValue', `${props.modelValue}<img src="${result.url}" alt="${escapeAttribute(alt)}">`)
    } else {
      editor.value.chain().focus().setImage({ src: result.url, alt }).run()
    }
  } catch (err) {
    uploadError.value = err
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="rich-text-field">
    <span :id="labelId" class="field-label">{{ t('manage.fields.content') }}</span>
    <div v-if="editor" class="rich-text-toolbar" role="toolbar" :aria-label="t('manage.toolbar.label')">
      <template v-if="!sourceMode">
        <button
          v-for="control in controls"
          :key="control.key"
          type="button"
          :class="{ active: control.active() }"
          :aria-label="t(`manage.toolbar.${control.key}`)"
          :title="t(`manage.toolbar.${control.key}`)"
          :aria-pressed="control.active()"
          :disabled="disabled"
          @click="control.command"
        >{{ control.text }}</button>
      </template>
      <button
        type="button"
        :aria-label="t('manage.toolbar.image')"
        :title="t('manage.toolbar.image')"
        :disabled="disabled || uploading"
        @click="imageInput?.click()"
      >{{ uploading ? '…' : 'IMG' }}</button>
      <input
        ref="imageInput"
        class="sr-only"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-hidden="true"
        tabindex="-1"
        @change="uploadImage"
      >
      <button
        type="button"
        :class="{ active: sourceMode }"
        :aria-label="t('manage.toolbar.source')"
        :title="t('manage.toolbar.source')"
        :aria-pressed="sourceMode"
        :disabled="disabled"
        @click="toggleSourceMode"
      >&lt;/&gt;</button>
      <span class="toolbar-spacer" aria-hidden="true"></span>
      <template v-if="!sourceMode">
        <button type="button" :aria-label="t('manage.toolbar.undo')" :title="t('manage.toolbar.undo')" :disabled="disabled || !editor.can().chain().focus().undo().run()" @click="editor.chain().focus().undo().run()">↶</button>
        <button type="button" :aria-label="t('manage.toolbar.redo')" :title="t('manage.toolbar.redo')" :disabled="disabled || !editor.can().chain().focus().redo().run()" @click="editor.chain().focus().redo().run()">↷</button>
      </template>
    </div>
    <textarea
      v-if="sourceMode"
      class="rich-text-editor rich-text-source"
      :value="modelValue"
      :disabled="disabled"
      spellcheck="false"
      :aria-labelledby="labelId"
      @input="emit('update:modelValue', $event.target.value)"
    ></textarea>
    <EditorContent v-else :editor="editor" class="rich-text-editor" />
    <p v-if="uploadError" class="inline-error rich-text-error" role="alert">{{ localizedUploadError }}</p>
  </div>
</template>
