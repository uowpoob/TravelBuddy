import { ApiError } from '../../api/auth'

type Position = [number, number]
export interface AmapMarker {
  on(event: string, handler: () => void): void
  setContent(content: HTMLElement): void
}
export interface AmapMap {
  add(overlays: unknown[]): void
  remove(overlays: unknown[]): void
  destroy(): void
  setFitView(
    overlays?: unknown[],
    immediately?: boolean,
    padding?: number[],
    maxZoom?: number,
  ): void
  setZoomAndCenter(zoom: number, position: Position): void
}
export interface AmapSdk {
  Map: new (container: HTMLElement, options: Record<string, unknown>) => AmapMap
  Marker: new (options: Record<string, unknown>) => AmapMarker
  Polyline: new (options: Record<string, unknown>) => unknown
  Pixel: new (x: number, y: number) => unknown
  InfoWindow: new (options: Record<string, unknown>) => {
    open(map: AmapMap, position: Position): void
    close(): void
  }
}
declare global {
  interface Window {
    AMap?: AmapSdk
    _AMapSecurityConfig?: { serviceHost: string }
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
let sdkPromise: Promise<AmapSdk> | null = null

export async function loadAmap(token: string): Promise<AmapSdk> {
  if (sdkPromise) return sdkPromise
  sdkPromise = (async () => {
    let response: Response
    try {
      response = await fetch(`${baseUrl}/api/v1/maps/config`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(15_000),
      })
    } catch {
      throw new ApiError(0, '地图配置加载失败，请稍后重试。')
    }
    const config = await response.json().catch(() => null)
    if (!response.ok) throw new ApiError(response.status, config?.detail || '地图配置尚未就绪。')
    window._AMapSecurityConfig = {
      serviceHost: new URL(`${baseUrl}${config.service_path}`, window.location.origin).href,
    }
    if (window.AMap) return window.AMap
    return new Promise<AmapSdk>((resolve, reject) => {
      const script = document.createElement('script')
      const timeout = window.setTimeout(() => fail(), 20_000)
      const fail = () => {
        window.clearTimeout(timeout)
        script.remove()
        reject(new Error('高德地图加载失败，请检查网络后重试。'))
      }
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(config.key)}`
      script.async = true
      script.onerror = fail
      script.onload = () => {
        window.clearTimeout(timeout)
        if (window.AMap) resolve(window.AMap)
        else fail()
      }
      document.head.append(script)
    })
  })().catch((failure) => {
    sdkPromise = null
    throw failure
  })
  return sdkPromise
}
