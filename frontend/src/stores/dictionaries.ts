import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { dictionaryApi } from '@/api/dictionaries'
import type { MeasurementUnit, ProjectSubitem } from '@/api/generated'

export const useDictionaryStore = defineStore('dictionaries', () => {
  const units = ref<MeasurementUnit[]>([])
  const projects = ref<ProjectSubitem[]>([])
  const loaded = ref(false)
  const unitOptions = computed(() =>
    units.value.filter((x) => x.enabled).map((x) => ({ label: x.name, value: x.id })),
  )

  async function load(force = false) {
    if (loaded.value && !force) return
    const [unitPage, projectPage] = await Promise.all([
      dictionaryApi.units({ page_size: 200 }),
      dictionaryApi.projects({ page_size: 200 }),
    ])
    units.value = unitPage.items
    projects.value = projectPage.items
    loaded.value = true
  }

  const getUnit = (id: number | null | undefined) => units.value.find((x) => x.id === id)
  return { units, projects, loaded, unitOptions, load, getUnit }
})
