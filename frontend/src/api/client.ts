import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default client

export interface Project {
  id: string
  name: string
  customer_name: string | null
  status: string
  currency: string
  margin_percent: number
  created_at: string
}

export interface Requirement {
  id: string
  category: string | null
  description: string
  quantity: number
  unit: string
  technical_attributes: Record<string, unknown>
  confidence: number
  matched_product_id: string | null
  reviewed: boolean
}

export interface BOQItem {
  id: string
  item_code: string | null
  description: string
  quantity: number
  unit: string
  unit_cost: number
  unit_price: number
  line_cost: number
  line_price: number
  margin_percent: number
  rule_trace: string[]
}

export interface PolicyDocument {
  id: string
  title: string
  filename: string
  uploaded_at: string
  ingested: boolean
  chunk_count: number
}

export interface PolicySource {
  document_title: string
  chunk_index: number
  excerpt: string
  similarity: number
}

export interface PolicyAskResponse {
  answer: string
  sources: PolicySource[]
  grounded: boolean
}
