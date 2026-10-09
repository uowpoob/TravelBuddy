import type { Place } from '../../types/conversation'

export function placeCoordinates(place: Place): [number, number] | null {
  if (place.source.toLowerCase() !== 'amap') return null
  const parts = place.location.split(',').map((part) => part.trim())
  if (parts.length !== 2 || parts.some((part) => !part)) return null
  const [longitude, latitude] = parts.map(Number)
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null
  if (Math.abs(longitude) > 180 || Math.abs(latitude) > 90) return null
  // 高德地点和底图都使用 GCJ-02，保持经度在前，无需坐标系转换。
  return [longitude, latitude]
}
