import { ref } from 'vue'
import { messages } from './messages.js'

export const DEFAULT_LOCALE = 'zh-CN'
export const SUPPORTED_LOCALES = Object.freeze(['zh-CN', 'en-US'])
export const localeOptions = Object.freeze([
  { value: 'zh-CN', labelKey: 'language.chinese' },
  { value: 'en-US', labelKey: 'language.english' },
])

const LOCALE_STORAGE_KEY = 'zio.locale'

function storedLocale() {
  if (typeof window === 'undefined') return DEFAULT_LOCALE
  try {
    const value = window.localStorage.getItem(LOCALE_STORAGE_KEY)
    return SUPPORTED_LOCALES.includes(value) ? value : DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}

function resolveMessage(source, key) {
  return key.split('.').reduce((value, part) => value?.[part], source)
}

function interpolate(value, params = {}) {
  return String(value).replace(/\{([\w.-]+)\}/g, (_, key) => {
    const replacement = key.split('.').reduce((result, part) => result?.[part], params)
    return replacement === undefined || replacement === null ? `{${key}}` : String(replacement)
  })
}

export const locale = ref(storedLocale())

function syncDocumentLocale(value) {
  if (typeof document !== 'undefined') document.documentElement.lang = value
}

syncDocumentLocale(locale.value)

export function setLocale(value) {
  const next = SUPPORTED_LOCALES.includes(value) ? value : DEFAULT_LOCALE
  locale.value = next
  syncDocumentLocale(next)
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      // 受限的存储环境不应阻止界面切换语言。
    }
  }
}

export function t(key, params) {
  const value = resolveMessage(messages[locale.value], key) ?? resolveMessage(messages[DEFAULT_LOCALE], key)
  return value === undefined ? key : interpolate(value, params)
}

export function d(value, options = {}, timeZone) {
  if (!value) return ''
  const dateOptions = timeZone ? { ...options, timeZone } : options
  return new Intl.DateTimeFormat(locale.value, dateOptions).format(new Date(value))
}

export function categoryLabel(code, fallback = code) {
  return resolveMessage(messages[locale.value], `category.${code}`) || fallback
}

const API_ERROR_KEYS = {
  request_failed: 'errors.requestFailed',
  network_error: 'errors.network',
  authentication_required: 'errors.authenticationRequired',
  origin_check_failed: 'errors.originCheckFailed',
  invalid_credentials: 'errors.invalidCredentials',
  invalid_username: 'errors.invalidUsername',
  password_length: 'errors.passwordLength',
  password_complexity: 'errors.passwordComplexity',
  user_exists: 'errors.userExists',
  not_found: 'errors.notFound',
  static_page_not_found: 'errors.staticPageNotFound',
  poster_not_found: 'errors.posterNotFound',
  cursor_invalid: 'errors.cursorInvalid',
  cursor_scope_mismatch: 'errors.cursorScopeMismatch',
  validation_error: 'errors.validation',
  invalid_input: 'errors.invalidInput',
  input_too_long: 'errors.inputTooLong',
  input_too_large: 'errors.inputTooLarge',
  invalid_timestamp: 'errors.invalidTimestamp',
  invalid_interval: 'errors.invalidInterval',
  duplicate_category: 'errors.duplicateCategory',
  primary_category_required: 'errors.primaryCategoryRequired',
  category_not_found: 'errors.categoryNotFound',
  duplicate_item: 'errors.duplicateItem',
  item_not_found: 'errors.itemNotFound',
  duplicate_tag: 'errors.duplicateTag',
  tag_not_found: 'errors.tagNotFound',
  private_item_link: 'errors.privateItemLink',
  private_item: 'errors.privateItem',
  invalid_item_category: 'errors.invalidItemCategory',
  invalid_parent_category: 'errors.invalidParentCategory',
  root_category_immutable: 'errors.rootCategoryImmutable',
  category_in_use: 'errors.categoryInUse',
  invalid_static_path: 'errors.invalidStaticPath',
  invalid_metadata: 'errors.invalidMetadata',
  invalid_timezone: 'errors.invalidTimezone',
  invalid_poster: 'errors.invalidPoster',
  poster_too_large: 'errors.posterTooLarge',
  poster_upload_failed: 'manage.errors.posterUploadFailed',
  frontend_not_built: 'errors.frontendNotBuilt',
}

export function errorKey(error) {
  if (typeof error === 'string') return 'errors.requestFailed'
  return API_ERROR_KEYS[error?.code] || (error?.status === 401 ? 'errors.authenticationRequired' : 'errors.requestFailed')
}

export function errorMessage(error) {
  return t(errorKey(error))
}

export function useI18n() {
  return {
    locale,
    locales: SUPPORTED_LOCALES,
    localeOptions,
    t,
    d,
    setLocale,
    categoryLabel,
    errorKey,
    errorMessage,
  }
}
