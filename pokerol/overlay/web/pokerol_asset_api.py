"""Narrow CORS endpoint used by the public Fakemon creator.

The endpoint can only write whitelisted Fakemon visual slots under the shared
POKEROL persistent asset root. It cannot address arbitrary filesystem paths or
write database content.
"""

import json
from urllib.parse import urlparse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from services.pokemon_asset_storage import (
    MAX_ASSET_BYTES,
    VIDEO_SLOTS,
    VISUAL_SLOTS,
    clear_slot,
    save_upload,
)

ALLOWED_ORIGINS = {
    "https://kendarte.github.io",
    "https://pokerol-game-production.up.railway.app",
    "http://127.0.0.1:4001",
    "http://localhost:4001",
}


def _origin(request):
    return str(request.headers.get("Origin") or "").rstrip("/")


def _origin_allowed(request):
    origin = _origin(request)
    if origin in ALLOWED_ORIGINS:
        return True
    # Same-origin requests may arrive without Origin. Keep cross-origin calls
    # locked to the explicit creator/production origins above.
    if not origin:
        referer = str(request.headers.get("Referer") or "")
        if not referer:
            return True
        parsed = urlparse(referer)
        candidate = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return candidate in ALLOWED_ORIGINS
    return False


def _json(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return {}


def _response(request, payload, status=200):
    response = JsonResponse(payload, status=status)
    origin = _origin(request)
    if origin in ALLOWED_ORIGINS:
        response["Access-Control-Allow-Origin"] = origin
        response["Vary"] = "Origin"
    response["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    response["Access-Control-Max-Age"] = "600"
    response["Cache-Control"] = "no-store"
    return response


def _reject_origin(request):
    return _response(request, {"ok": False, "error": "origin no permitido"}, 403)


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def pokemon_asset_health(request):
    if request.method == "OPTIONS":
        return _response(request, {"ok": True}) if _origin_allowed(request) else _reject_origin(request)
    if not _origin_allowed(request):
        return _reject_origin(request)
    return _response(request, {
        "ok": True,
        "service": "pokerol-pokemon-assets",
        "max_bytes": MAX_ASSET_BYTES,
        "slots": sorted(VISUAL_SLOTS),
        "video_slots": sorted(VIDEO_SLOTS),
    })


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def pokemon_asset_upload(request):
    if request.method == "OPTIONS":
        return _response(request, {"ok": True}) if _origin_allowed(request) else _reject_origin(request)
    if not _origin_allowed(request):
        return _reject_origin(request)
    upload = request.FILES.get("file")
    if upload is None:
        return _response(request, {"ok": False, "error": "falta archivo"}, 400)
    species_id = request.POST.get("species_id")
    slot = request.POST.get("slot")
    media_kind = request.POST.get("media_kind") or "image"
    try:
        src = save_upload(upload, species_id, slot, media_kind)
    except (ValueError, OSError) as exc:
        return _response(request, {"ok": False, "error": str(exc)}, 400)
    return _response(request, {
        "ok": True,
        "status": "GUARDADO",
        "species_id": str(species_id or "").strip(),
        "slot": str(slot or "").strip().lower(),
        "media_kind": str(media_kind or "image").strip().lower(),
        "src": src,
    })


@csrf_exempt
@require_http_methods(["POST", "DELETE", "OPTIONS"])
def pokemon_asset_clear(request):
    if request.method == "OPTIONS":
        return _response(request, {"ok": True}) if _origin_allowed(request) else _reject_origin(request)
    if not _origin_allowed(request):
        return _reject_origin(request)
    data = request.POST if request.POST else _json(request)
    species_id = data.get("species_id")
    slot = data.get("slot")
    media_kind = data.get("media_kind") or None
    try:
        removed = clear_slot(species_id, slot, media_kind)
    except (ValueError, OSError) as exc:
        return _response(request, {"ok": False, "error": str(exc)}, 400)
    return _response(request, {
        "ok": True,
        "status": "RESET",
        "species_id": str(species_id or "").strip(),
        "slot": str(slot or "").strip().lower(),
        "media_kind": str(media_kind or "").strip().lower() or None,
        "removed": removed,
    })
