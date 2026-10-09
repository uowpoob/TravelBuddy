export interface UserPublic {
  id: number
  username: string
  created_at: string
}

export interface Credentials {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: UserPublic
}

export interface StoredSession {
  token: string
  expiresAt: number
}
