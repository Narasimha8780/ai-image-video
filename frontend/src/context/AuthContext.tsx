import React, { createContext, useContext, useEffect, useState } from 'react'
import { api, getStoredToken, setStoredToken } from '../api/client'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  googleSignIn: (idToken: string, email?: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = async () => {
    const token = getStoredToken()
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await api.me()
      setUser(me)
    } catch {
      setStoredToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshUser()
  }, [])

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password)
    setStoredToken(res.access_token)
    setUser(res.user)
  }

  const register = async (email: string, password: string, displayName: string) => {
    const res = await api.register(email, password, displayName)
    setStoredToken(res.access_token)
    setUser(res.user)
  }

  const googleSignIn = async (idToken: string, email?: string) => {
    const res = await api.googleSignIn(idToken, email)
    setStoredToken(res.access_token)
    setUser(res.user)
  }

  const logout = () => {
    setStoredToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, googleSignIn, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
