"""Opt-in production smoke test for persistent Fakemon visuals.

Run only when POKEROL_ASSET_SMOKE_TEST=1. It talks to the local production HTTP
stack, creates a disposable species asset folder, verifies the visual registry
normalizer and battle-shot director in-process, then clears every test asset.
It never creates or edits a player, room, or persistent species registry row.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

BASE = os.environ.get("POKEROL_SMOKE_BASE_URL", "http://127.0.0.1:4001").rstrip("/")
SPECIES_ID = "SMOKE-ASSET-" + uuid4().hex[:10].upper()
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZVtQAAAAASUVORK5CYII="
)
SLOTS = ("battle_front", "battle_back", "shot_attack_special", "shot_hit")


def log(message):
    print(f"[POKEROL-SMOKE] {message}", flush=True)


def request_json(path, *, data=None, headers=None, method=None, timeout=10):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"HTTP {response.status}: {raw[:200]!r}")
    return json.loads(raw.decode("utf-8"))


def multipart(fields, filename, file_bytes, mime="image/png"):
    boundary = "----POKEROLSmoke" + uuid4().hex
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def upload(slot, marker="a"):
    body, headers = multipart(
        {"species_id": SPECIES_ID, "slot": slot, "media_kind": "image"},
        f"{slot}-{marker}.png",
        PNG,
    )
    data = request_json("/pokerol-api/assets/pokemon/upload", data=body, headers=headers, method="POST")
    src = str(data.get("src") or "")
    expected = f"/pokerol-assets/pokemon/{SPECIES_ID}/{slot}-"
    if not data.get("ok") or not src.startswith(expected) or not src.endswith(".png"):
        raise AssertionError(f"upload inválido para {slot}: {data}")
    return src


def fetch_asset(src):
    with urllib.request.urlopen(BASE + src, timeout=10) as response:
        payload = response.read()
        if response.status != 200 or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AssertionError(f"asset no servible: {src} HTTP={response.status}")


def clear(slot):
    payload = json.dumps({"species_id": SPECIES_ID, "slot": slot, "media_kind": "image"}).encode()
    data = request_json(
        "/pokerol-api/assets/pokemon/clear",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if not data.get("ok"):
        raise AssertionError(f"clear inválido para {slot}: {data}")


def verify_registry_and_shots(refs):
    runtime = Path(__file__).resolve().parent
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
    import django
    django.setup()

    from services.pokemon_species_registry import normalize_move_template, normalize_species_template
    from services.pokemon_battle_shot_director import build_battle_shots

    visual_pack = {
        "battle_front": {"src": refs["battle_front"], "scale": 1.0, "anchor_x": 0.5, "anchor_y": 1.0},
        "battle_back": {"src": refs["battle_back"], "scale": 1.0, "anchor_x": 0.5, "anchor_y": 1.0},
        "shot_attack_special": {"src": refs["shot_attack_special"], "scale": 1.0, "anchor_x": 0.5, "anchor_y": 1.0},
        "shot_hit": {"src": refs["shot_hit"], "scale": 1.0, "anchor_x": 0.5, "anchor_y": 1.0},
    }
    species = normalize_species_template({
        "species_id": SPECIES_ID,
        "species_name": "Smoke Fakemon",
        "sprite": {"front": refs["battle_front"], "back": refs["battle_back"], "scale": 1.0},
        "combat_visuals": {
            "battle": {"front": refs["battle_front"], "back": refs["battle_back"], "scale": 1.0},
            "shots": {
                "attack_special": {"image": refs["shot_attack_special"], "scale": 1.0, "anchor_x": 50, "anchor_y": 100},
                "hit": {"image": refs["shot_hit"], "scale": 1.0, "anchor_x": 50, "anchor_y": 100},
            },
        },
        "visual_pack": visual_pack,
        "known_moves": ["SMOKE-SPECIAL"],
    })
    if species.get("visual_pack", {}).get("battle_front", {}).get("src") != refs["battle_front"]:
        raise AssertionError("species registry normalizer perdió visual_pack")
    if species.get("sprite", {}).get("back") != refs["battle_back"]:
        raise AssertionError("species registry normalizer perdió battle_back")
    if species.get("combat_visuals", {}).get("shots", {}).get("attack_special", {}).get("image") != refs["shot_attack_special"]:
        raise AssertionError("species registry normalizer perdió shot_attack_special")
    if species.get("combat_visuals", {}).get("shots", {}).get("hit", {}).get("image") != refs["shot_hit"]:
        raise AssertionError("species registry normalizer perdió shot_hit")

    move = normalize_move_template({
        "move_id": "SMOKE-SPECIAL",
        "name": "Smoke Special",
        "damage_class": "SPECIAL",
        "power": 50,
        "accuracy": 100,
        "pp": 10,
        "trajectory": "DIRECT",
        "range": "MID",
        "combat_profile": {"power": 3, "control": 3, "speed": 3},
        "resolution": {"default_stat": "COO", "modes": ["CONFRONT"], "max_checks": 1},
        "visual": {"pose_family": "ATTACK_SPECIAL"},
    })
    profile = dict(species)
    profile["moves"] = [move]
    profile["resolved_moves"] = [move]
    before = {
        "battle_id": "SMOKE-BATTLE",
        "turn": 1,
        "site": {"name": "Smoke Room"},
        "player": {"entity_id": "PLAYER-SMOKE", "name": "Smoke Fakemon", "moves": [move]},
        "enemy": {"entity_id": "ENEMY-SMOKE", "name": "Smoke Fakemon", "moves": [move]},
        "_source_player_profile": profile,
        "_source_enemy_profile": profile,
    }
    after = dict(before)
    after["log"] = [{"kind": "DAMAGE", "actor": "PLAYER-SMOKE", "text": "Smoke impact"}]
    packet = build_battle_shots(before, after, {"type": "MOVE", "move_id": "SMOKE-SPECIAL"}, log_start=0)
    shots = {row.get("shot"): row for row in packet.get("shots") or []}
    declaration = shots.get("DECLARATION_PLAYER") or {}
    execution = shots.get("EXECUTION") or {}
    impact = shots.get("IMPACT") or {}
    if declaration.get("media_src") != refs["battle_back"]:
        raise AssertionError(f"battle view no eligió battle_back: {declaration.get('media_src')}")
    if execution.get("media_src") != refs["shot_attack_special"]:
        raise AssertionError(f"SPECIAL no eligió shot_attack_special: {execution.get('media_src')}")
    if impact.get("media_src") != refs["shot_hit"]:
        raise AssertionError(f"HIT no eligió shot_hit: {impact.get('media_src')}")


def wait_for_server():
    last = None
    for _ in range(80):
        try:
            data = request_json("/pokerol-api/assets/pokemon/health", timeout=2)
            if data.get("ok"):
                return data
        except Exception as exc:
            last = exc
        time.sleep(0.5)
    raise RuntimeError(f"asset API no respondió: {last}")


def main():
    refs = {}
    try:
        health = wait_for_server()
        log(f"HEALTH OK slots={len(health.get('slots') or [])}")
        for slot in SLOTS:
            refs[slot] = upload(slot)
            fetch_asset(refs[slot])
            log(f"UPLOAD+SERVE OK {slot} -> {refs[slot]}")

        old_front = refs["battle_front"]
        refs["battle_front"] = upload("battle_front", "replacement")
        fetch_asset(refs["battle_front"])
        if refs["battle_front"] == old_front:
            raise AssertionError("reemplazo reutilizó URL immutable")
        log(f"REPLACE OK battle_front {old_front} -> {refs['battle_front']}")

        verify_registry_and_shots(refs)
        log("REGISTRY NORMALIZE OK visual_pack/sprite/combat_visuals")
        log("SHOT DIRECTOR OK battle_back -> shot_attack_special -> shot_hit")
        log("RESULT SUCCESS")
    finally:
        for slot in SLOTS:
            try:
                clear(slot)
            except Exception as exc:
                log(f"CLEANUP WARNING {slot}: {exc}")
        log(f"CLEANUP COMPLETE species={SPECIES_ID}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"RESULT ERROR {type(exc).__name__}: {exc}")
        raise
