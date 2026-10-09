from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.app.api.dependencies import get_current_user
from backend.app.models import User

router = APIRouter(prefix="/api/v1/maps", tags=["maps"])


@router.get("/config")
async def map_config(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    client = getattr(request.app.state, "amap_route_client", None)
    if (
        client is None
        or not client.settings.GD_JSAPI_KEY.strip()
        or not client.settings.GD_JSAPI_SECURITY_CODE.get_secret_value().strip()
    ):
        raise HTTPException(
            status_code=503,
            detail="请配置 GD_JSAPI_KEY 和 GD_JSAPI_SECURITY_CODE 后重启服务。",
        )
    return {
        "key": client.settings.GD_JSAPI_KEY,
        "service_path": "/api/v1/maps/_AMapService",
    }


@router.get("/_AMapService/{path:path}")
async def proxy_map_service(path: str, request: Request) -> Response:
    # JS SDK 无法附加 Bearer 请求头，仅允许底图初始化所需的固定路径。
    targets = {
        "v4/map/styles": "https://webapi.amap.com/v4/map/styles",
        "v4/maps": "https://restapi.amap.com/v4/maps",
    }
    if path not in targets or len(request.url.query) > 4096:
        raise HTTPException(status_code=404, detail="地图服务路径不可用。")
    client = getattr(request.app.state, "amap_route_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="地图服务未配置。")
    settings = client.settings
    if (
        not settings.GD_JSAPI_KEY
        or not settings.GD_JSAPI_SECURITY_CODE.get_secret_value()
    ):
        raise HTTPException(status_code=503, detail="地图服务未配置。")
    if request.query_params.get("key") != settings.GD_JSAPI_KEY:
        raise HTTPException(status_code=403, detail="地图 Key 不匹配。")
    params = dict(request.query_params)
    params["jscode"] = settings.GD_JSAPI_SECURITY_CODE.get_secret_value()
    try:
        response = await client.http.get(targets[path], params=params)
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502, detail="地图底图服务暂时不可用。"
        ) from None
    return Response(
        content=response.content,
        headers={
            "Content-Type": response.headers.get("content-type", "application/json"),
            "Cache-Control": "private, max-age=60",
        },
    )
