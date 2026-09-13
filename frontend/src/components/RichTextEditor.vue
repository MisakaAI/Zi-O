<script setup>
import { onBeforeUnmount, useId, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { useI18n } from '../i18n'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const labelId = `rich-text-${useId()}`

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  extensions: [StarterKit.configure({ heading: { levels: [2, 3] } })],
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
</script>

<template>
  <div class="rich-text-field">
    <span :id="labelId" class="field-label">{{ t('manage.fields.content') }}</span>
    <div v-if="editor" class="rich-text-toolbar" role="toolbar" :aria-label="t('manage.toolbar.label')">
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
      <span class="toolbar-spacer" aria-hidden="true"></span>
      <button type="button" :aria-label="t('manage.toolbar.undo')" :title="t('manage.toolbar.undo')" :disabled="disabled || !editor.can().chain().focus().undo().run()" @click="editor.chain().focus().undo().run()">↶</button>
      <button type="button" :aria-label="t('manage.toolbar.redo')" :title="t('manage.toolbar.redo')" :disabled="disabled || !editor.can().chain().focus().redo().run()" @click="editor.chain().focus().redo().run()">↷</button>
    </div>
    <EditorContent :editor="editor" class="rich-text-editor" />
  </div>
</template>
