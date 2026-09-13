<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RiArrowDropLeftLine, RiArrowDropRightLine } from '@remixicon/vue'
import { get } from '../api/client'
import StateMessage from './StateMessage.vue'
import { useI18n } from '../i18n'

const props = defineProps({
  referenceDate: { type: [String, Date], required: true },
  timezone: { type: String, default: 'UTC' },
})

const { d, errorKey, locale, t } = useI18n()
const month = ref('')
const counts = ref({})
const loading = ref(true)
const error = ref(null)
const manuallySelectedMonth = ref(false)
const yearPickerOpen = ref(false)
const yearPickerYear = ref(0)
const yearCalendarCounts = ref({})
const yearCalendarLoading = ref(false)
const yearCalendarError = ref(null)
const calendarRoot = ref(null)
const titleButton = ref(null)
const yearPickerDialog = ref(null)
let requestSerial = 0
let yearRequestSerial = 0
const yearCountCache = new Map()

function intlParts(value, options, timezone) {
  const parts = new Intl.DateTimeFormat('en-US', { ...options, timeZone: timezone }).formatToParts(new Date(value))
  return Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]))
}

function monthFromInstant(value, timezone) {
  try {
    const parts = intlParts(value, { year: 'numeric', month: '2-digit' }, timezone)
    return `${parts.year}-${parts.month}`
  } catch {
    const parts = intlParts(value, { year: 'numeric', month: '2-digit' }, 'UTC')
    return `${parts.year}-${parts.month}`
  }
}

function dateFromInstant(value, timezone) {
  try {
    const parts = intlParts(value, { year: 'numeric', month: '2-digit', day: '2-digit' }, timezone)
    return `${parts.year}-${parts.month}-${parts.day}`
  } catch {
    const parts = intlParts(value, { year: 'numeric', month: '2-digit', day: '2-digit' }, 'UTC')
    return `${parts.year}-${parts.month}-${parts.day}`
  }
}

function parseMonth(value) {
  const match = /^(\d{4})-(\d{2})$/.exec(value)
  if (!match) return null
  return { year: Number(match[1]), monthIndex: Number(match[2]) - 1 }
}

function monthKey(year, monthIndex) {
  return `${year}-${String(monthIndex + 1).padStart(2, '0')}`
}

function shiftMonth(value, offset) {
  const parsed = parseMonth(value)
  if (!parsed) return value
  const shifted = new Date(Date.UTC(parsed.year, parsed.monthIndex + offset, 1))
  return monthKey(shifted.getUTCFullYear(), shifted.getUTCMonth())
}

function dateKeyFromUtcDate(value) {
  return [value.getUTCFullYear(), String(value.getUTCMonth() + 1).padStart(2, '0'), String(value.getUTCDate()).padStart(2, '0')].join('-')
}

function dateObject(dateKey) {
  return new Date(`${dateKey}T12:00:00.000Z`)
}

function buildCalendarDays(monthValue, dayCounts = {}, maxCountOverride = null) {
  const parsed = parseMonth(monthValue)
  if (!parsed) return []
  const first = new Date(Date.UTC(parsed.year, parsed.monthIndex, 1))
  const daysInMonth = new Date(Date.UTC(parsed.year, parsed.monthIndex + 1, 0)).getUTCDate()
  const leadingDays = (first.getUTCDay() + 6) % 7
  const totalDays = Math.ceil((leadingDays + daysInMonth) / 7) * 7
  const maxCount = maxCountOverride ?? Math.max(0, ...Object.values(dayCounts))
  return Array.from({ length: totalDays }, (_, index) => {
    const date = new Date(Date.UTC(parsed.year, parsed.monthIndex, index - leadingDays + 1))
    const dateKey = dateKeyFromUtcDate(date)
    const isCurrentMonth = index >= leadingDays && index < leadingDays + daysInMonth
    const count = isCurrentMonth ? dayCounts[dateKey] || 0 : 0
    const ratio = maxCount ? count / maxCount : 0
    const level = count === 0 ? 0 : maxCount === 1 || ratio >= .75 ? 4 : ratio >= .5 ? 3 : ratio >= .25 ? 2 : 1
    return { date: dateKey, label: date.getUTCDate(), count, level, isCurrentMonth, isToday: isCurrentMonth && dateKey === todayKey.value }
  })
}

const currentMonth = computed(() => monthFromInstant(props.referenceDate, props.timezone))
const todayKey = computed(() => dateFromInstant(props.referenceDate, props.timezone))
const currentYear = computed(() => Number(currentMonth.value.slice(0, 4)))
const monthLabel = computed(() => {
  const parsed = parseMonth(month.value)
  return parsed ? d(new Date(Date.UTC(parsed.year, parsed.monthIndex, 15, 12)), { year: 'numeric', month: 'long' }, props.timezone) : month.value
})
const weekdayLabels = computed(() => locale.value === 'zh-CN' ? ['一', '二', '三', '四', '五', '六', '日'] : ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'])
const calendarDays = computed(() => buildCalendarDays(month.value, counts.value))
const yearCalendarMonths = computed(() => {
  const year = yearPickerYear.value || currentYear.value
  const months = yearCalendarCounts.value[year] || {}
  const maxCount = Math.max(0, ...Object.values(months).flatMap((days) => Object.values(days)))
  return Array.from({ length: 12 }, (_, monthIndex) => {
    const key = monthKey(year, monthIndex)
    const monthDate = new Date(Date.UTC(year, monthIndex, 15, 12))
    const monthDays = months[key] || {}
    return {
      key,
      label: d(monthDate, { month: 'short' }, props.timezone),
      fullLabel: d(monthDate, { year: 'numeric', month: 'long' }, props.timezone),
      days: buildCalendarDays(key, monthDays, maxCount),
      isShown: key === month.value,
      isCurrent: key === currentMonth.value,
    }
  })
})
const monthEventCount = computed(() => Object.values(counts.value).reduce((sum, count) => sum + count, 0))
const activeDayCount = computed(() => Object.keys(counts.value).length)
const localizedError = computed(() => error.value ? t(errorKey(error.value)) : '')
const localizedYearError = computed(() => yearCalendarError.value ? t(errorKey(yearCalendarError.value)) : '')

function dayLabel(day) {
  const dateLabel = d(dateObject(day.date), { dateStyle: 'full' }, 'UTC')
  return day.count ? `${dateLabel} · ${t('now.calendarEvents', { count: day.count })}` : `${dateLabel} · ${t('now.calendarNoEvents')}`
}

async function loadMonth() {
  const parsed = parseMonth(month.value)
  if (!parsed) return
  const serial = ++requestSerial
  loading.value = true
  error.value = null
  try {
    const data = await get(`/api/public/calendar?year=${parsed.year}&month=${parsed.monthIndex + 1}`)
    if (serial !== requestSerial) return
    counts.value = Object.fromEntries((data.days || []).map((day) => [day.date, day.count]))
  } catch (err) {
    if (serial === requestSerial) error.value = err
  } finally {
    if (serial === requestSerial) loading.value = false
  }
}

async function loadYear(year) {
  const serial = ++yearRequestSerial
  const cached = yearCountCache.get(year)
  if (cached) {
    yearCalendarCounts.value = { ...yearCalendarCounts.value, [year]: cached }
    yearCalendarError.value = null
    yearCalendarLoading.value = false
    return
  }
  yearCalendarLoading.value = true
  yearCalendarError.value = null
  try {
    const responses = await Promise.all(Array.from({ length: 12 }, (_, monthIndex) => get(`/api/public/calendar?year=${year}&month=${monthIndex + 1}`)))
    if (serial !== yearRequestSerial) return
    const months = Object.fromEntries(responses.map((data, monthIndex) => [
      monthKey(year, monthIndex), Object.fromEntries((data.days || []).map((day) => [day.date, day.count])),
    ]))
    yearCountCache.set(year, months)
    yearCalendarCounts.value = { ...yearCalendarCounts.value, [year]: months }
  } catch (err) {
    if (serial === yearRequestSerial) yearCalendarError.value = err
  } finally {
    if (serial === yearRequestSerial) yearCalendarLoading.value = false
  }
}

function selectMonth(next, manual = true) {
  if (!next || next === month.value) return
  manuallySelectedMonth.value = manual
  month.value = next
  loadMonth()
}

function moveMonth(offset) { selectMonth(shiftMonth(month.value, offset)) }
function showCurrentMonth() {
  manuallySelectedMonth.value = false
  if (month.value === currentMonth.value) { loadMonth(); return }
  month.value = currentMonth.value
  loadMonth()
}

function closeYearPicker(restoreFocus = false) {
  yearPickerOpen.value = false
  if (restoreFocus) nextTick(() => titleButton.value?.focus())
}

function toggleYearPicker() {
  if (yearPickerOpen.value) {
    closeYearPicker(true)
    return
  }
  yearPickerYear.value = currentYear.value
  yearPickerOpen.value = true
  loadYear(yearPickerYear.value)
  nextTick(() => yearPickerDialog.value?.focus())
}

function moveYear(offset) {
  const next = yearPickerYear.value + offset
  if (next >= 1 && next <= 9998) {
    yearPickerYear.value = next
    loadYear(next)
  }
}

function showCurrentYear() {
  if (yearPickerYear.value === currentYear.value) return
  yearPickerYear.value = currentYear.value
  loadYear(yearPickerYear.value)
}

function chooseYearMonth(key) {
  if (key !== month.value) selectMonth(key)
  closeYearPicker(true)
}

function closeYearPickerOnOutsideClick(event) {
  if (yearPickerOpen.value && !calendarRoot.value?.contains(event.target)) closeYearPicker()
}

watch(currentMonth, (next) => {
  if (!month.value) {
    month.value = next
    loadMonth()
  } else if (!manuallySelectedMonth.value && month.value !== next) {
    month.value = next
    loadMonth()
  }
})

onMounted(() => {
  month.value = currentMonth.value
  loadMonth()
  document.addEventListener('pointerdown', closeYearPickerOnOutsideClick)
})

onUnmounted(() => document.removeEventListener('pointerdown', closeYearPickerOnOutsideClick))
</script>

<template>
  <section ref="calendarRoot" class="calendar-panel" :aria-busy="loading" @keydown.esc="closeYearPicker(true)">
    <header class="calendar-header">
      <div>
        <h2 class="calendar-heading">
          <button
            ref="titleButton"
            :id="`calendar-title-${month}`"
            type="button"
            class="calendar-title calendar-title-button"
            :aria-label="t('now.calendarSelectMonth')"
            :aria-expanded="yearPickerOpen"
            aria-controls="calendar-year-picker"
            @click="toggleYearPicker"
          >
            {{ monthLabel }}
          </button>
        </h2>
      </div>
      <div class="calendar-controls">
        <button type="button" class="calendar-control" :aria-label="t('now.calendarPreviousMonth')" @click="moveMonth(-1)">
          <RiArrowDropLeftLine aria-hidden="true" focusable="false" />
        </button>
        <button type="button" class="calendar-control calendar-control-today" :disabled="month === currentMonth" :aria-label="t('now.calendarCurrentMonth')" @click="showCurrentMonth">
          {{ t('now.calendarToday') }}
        </button>
        <button type="button" class="calendar-control" :aria-label="t('now.calendarNextMonth')" @click="moveMonth(1)">
          <RiArrowDropRightLine aria-hidden="true" focusable="false" />
        </button>
      </div>
    </header>

    <div v-if="yearPickerOpen" class="calendar-year-backdrop" @click.self="closeYearPicker()">
      <section
        id="calendar-year-picker"
        ref="yearPickerDialog"
        class="calendar-year-picker"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`calendar-year-heading-${yearPickerYear}`"
        :aria-busy="yearCalendarLoading"
        tabindex="-1"
        @keydown.esc.stop.prevent="closeYearPicker(true)"
      >
        <header class="calendar-year-header">
          <h2 :id="`calendar-year-heading-${yearPickerYear}`" class="calendar-year-value mono">{{ yearPickerYear }}</h2>
          <div class="calendar-year-controls">
            <button type="button" class="calendar-control" :aria-label="t('now.calendarPreviousYear')" :disabled="yearPickerYear <= 1" @click="moveYear(-1)">
              <RiArrowDropLeftLine aria-hidden="true" focusable="false" />
            </button>
            <button type="button" class="calendar-control calendar-year-current" :aria-label="t('now.calendarCurrentYear')" :disabled="yearPickerYear === currentYear" @click="showCurrentYear">
              {{ t('now.calendarCurrentYear') }}
            </button>
            <button type="button" class="calendar-control" :aria-label="t('now.calendarNextYear')" :disabled="yearPickerYear >= 9998" @click="moveYear(1)">
              <RiArrowDropRightLine aria-hidden="true" focusable="false" />
            </button>
          </div>
        </header>

        <div v-if="yearCalendarError" class="calendar-year-status state-error" role="alert">
          <span>{{ localizedYearError }}</span>
          <button type="button" class="link-button" @click="loadYear(yearPickerYear)">{{ t('now.calendarRetry') }}</button>
        </div>
        <div v-else-if="yearCalendarLoading" class="calendar-year-status" role="status" aria-live="polite">
          <span class="state-mark" aria-hidden="true">…</span>
          <span>{{ t('now.calendarYearLoading') }}</span>
        </div>

        <div class="calendar-year-grid">
          <section
            v-for="monthOption in yearCalendarMonths"
            :key="monthOption.key"
            class="calendar-year-month-card"
            :class="{ 'calendar-year-month-card-shown': monthOption.isShown, 'calendar-year-month-card-current': monthOption.isCurrent }"
            :aria-label="monthOption.fullLabel"
          >
            <button
              type="button"
              class="calendar-year-month-title"
              :class="{ 'calendar-year-month-title-shown': monthOption.isShown }"
              :aria-label="`${t('now.calendarSelectMonth')}: ${monthOption.fullLabel}`"
              :aria-current="monthOption.isShown ? 'page' : undefined"
              @click="chooseYearMonth(monthOption.key)"
            >
              <span>{{ monthOption.label }}</span>
              <span v-if="monthOption.isCurrent" class="calendar-year-month-marker" aria-hidden="true"></span>
            </button>
            <div class="calendar-year-weekdays" aria-hidden="true">
              <span v-for="weekday in weekdayLabels" :key="weekday" class="calendar-year-weekday mono">{{ weekday }}</span>
            </div>
            <div class="calendar-year-days" role="grid" :aria-label="monthOption.fullLabel">
              <span
                v-for="day in monthOption.days"
                :key="day.date"
                class="calendar-year-day"
                :class="[
                  day.isCurrentMonth ? 'calendar-year-day-current' : 'calendar-year-day-outside',
                  day.level ? `calendar-year-day-level-${day.level}` : '',
                  { 'calendar-year-day-today': day.isToday },
                ]"
                role="gridcell"
                :aria-label="dayLabel(day)"
                :title="dayLabel(day)"
              >
                <time :datetime="day.date">{{ day.label }}</time>
              </span>
            </div>
          </section>
        </div>
      </section>
    </div>

    <StateMessage v-if="loading" type="loading" :message="t('now.calendarLoading')" />
    <StateMessage v-else-if="error" type="error" :message="localizedError" />
    <template v-else>
      <div class="calendar-weekdays" aria-hidden="true">
        <span v-for="weekday in weekdayLabels" :key="weekday" class="calendar-weekday mono">{{ weekday }}</span>
      </div>
      <div class="calendar-grid" role="grid" :aria-labelledby="`calendar-title-${month}`">
        <div
          v-for="day in calendarDays"
          :key="day.date"
          class="calendar-day"
          :class="[
            day.isCurrentMonth ? 'calendar-day-current' : 'calendar-day-outside',
            day.level ? `calendar-day-level-${day.level}` : '',
            { 'calendar-day-today': day.isToday },
          ]"
          role="gridcell"
          :aria-label="dayLabel(day)"
          :title="dayLabel(day)"
        >
          <time :datetime="day.date">{{ day.label }}</time>
          <span v-if="day.count" class="calendar-day-count mono" aria-hidden="true">{{ day.count > 99 ? '99+' : day.count }}</span>
        </div>
      </div>
      <div class="calendar-meta muted">
        <span class="calendar-legend-mark" aria-hidden="true"></span>
        <span v-if="monthEventCount">{{ t('now.calendarSummary', { days: activeDayCount, count: monthEventCount }) }}</span>
        <span v-else>{{ t('now.calendarNoEvents') }}</span>
      </div>
    </template>
  </section>
</template>
