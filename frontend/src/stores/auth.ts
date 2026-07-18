import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'
import type { LoginRequest, User } from '@/api/generated'
import type { Permission } from '@/types/navigation'
import { rolePermissions } from '@/types/navigation'

const savedUser = localStorage.getItem('auth_user')

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(savedUser ? JSON.parse(savedUser) : null)
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  function can(permission: Permission): boolean {
    return user.value ? rolePermissions[user.value.role].includes(permission) : false
  }

  async function login(payload: LoginRequest) {
    const response = await authApi.login(payload)
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('auth_user', JSON.stringify(response.user))
  }

  async function refresh() {
    if (!token.value) return
    user.value = await authApi.me()
    localStorage.setItem('auth_user', JSON.stringify(user.value))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('auth_user')
  }

  return { user, token, isAuthenticated, can, login, refresh, logout }
})
