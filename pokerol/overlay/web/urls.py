"""POKEROL web routes plus Evennia defaults."""

from django.urls import include, path
from evennia.web.urls import urlpatterns as evennia_default_urlpatterns

from web.pokerol_asset_api import (
    pokemon_asset_clear,
    pokemon_asset_health,
    pokemon_asset_upload,
)

urlpatterns = [
    path("pokerol-api/assets/pokemon/health", pokemon_asset_health, name="pokerol-pokemon-assets-health"),
    path("pokerol-api/assets/pokemon/upload", pokemon_asset_upload, name="pokerol-pokemon-assets-upload"),
    path("pokerol-api/assets/pokemon/clear", pokemon_asset_clear, name="pokerol-pokemon-assets-clear"),
    path("", include("web.website.urls")),
    path("webclient/", include("web.webclient.urls")),
    path("admin/", include("web.admin.urls")),
]

urlpatterns = urlpatterns + evennia_default_urlpatterns
