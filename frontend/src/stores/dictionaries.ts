import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { dictionaryApi } from '@/api/dictionaries'
import type { MeasurementUnit } from '@/api/generated'

export const useDictionaryStore = defineStore('dictionaries', () => {
  const units = ref<MeasurementUnit[]>([])
  const loaded = ref(false)
  const unitOptions = computed(() =>
    units.value.filter((x) => x.enabled).map((x) => ({ label: x.name, value: x.id })),
  )

  async function load(force = false) {
    if (loaded.value && !force) return
    const unitPage = await dictionaryApi.units({ page_size: 200 })
    units.value = unitPage.items
    loaded.value = true
  }

  const getUnit = (id: number | null | undefined) => units.value.find((x) => x.id === id)
  return { units, loaded, unitOptions, load, getUnit }
})
