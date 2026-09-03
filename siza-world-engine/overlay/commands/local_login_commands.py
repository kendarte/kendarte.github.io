from ipaddress import ip_address

from evennia import Command, search_object, search_tag
from evennia.accounts.models import AccountDB
from evennia.utils import utils
from twisted.internet import reactor

from services.dm_campaign_registry import start_registered_campaign
from world.darkhaven_tutorial_campaign import DARKHAVEN_TUTORIAL_CAMPAIGN


LOCAL_CHARACTER = "Nereida"
LOCAL_CAMPAIGN = str(DARKHAVEN_TUTORIAL_CAMPAIGN.get("id"))
ENTRY_ROOM = "Puerta de Darkhaven"
ENTRY_ROOM_ID = "DH7-ROOM-001"


def _client_host(session):
    address = getattr(session, "address", "")
    if isinstance(address, (tuple, list)) and address:
        return str(address[0] or "").strip()
    return str(address or "").split(",", 1)[0].strip()


def _is_loopback(session):
    host = _client_host(session)
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _candidate_score(account, character):
    score = 0
    campaign = getattr(character.db, "dm_campaign_state", None)
    location = getattr(character, "location", None)
    room_id = str(getattr(getattr(location, "db", None), "room_id", "") or "")

    if campaign:
        score += 100
        if str(campaign.get("campaign_id") or "") == LOCAL_CAMPAIGN:
            score += 1200
        progressed = bool(campaign.get("completed_beats")) or int(campaign.get("director_turn", 0) or 0) > 0
        if progressed:
            score += 300
    if room_id.startswith("DH7-ROOM-"):
        score += 900
    elif location:
        score += 100
    if str(getattr(character, "key", "") or "").lower() == LOCAL_CHARACTER.lower():
        score += 80
    if getattr(account.db, "_last_puppet", None) == character:
        score += 25
    if bool(getattr(account, "is_superuser", False)):
        score += 10
    return score


def _find_player():
    accounts = list(AccountDB.objects.all().order_by("id"))
    pairs = []
    for account in accounts:
        characters = list(utils.make_iter(account.characters))
        last = getattr(account.db, "_last_puppet", None)
        if last and last not in characters and last.access(account, "puppet"):
            characters.append(last)
        for character in characters:
            if character and character.access(account, "puppet"):
                pairs.append((account, character))

    if not pairs:
        named = [obj for obj in search_object(LOCAL_CHARACTER) if str(obj.key).lower() == LOCAL_CHARACTER.lower()]
        for account in accounts:
            if not bool(getattr(account, "is_superuser", False)):
                continue
            for character in named:
                if character.access(account, "puppet"):
                    pairs.append((account, character))

    if not pairs:
        return None, None
    return max(
        pairs,
        key=lambda pair: (_candidate_score(pair[0], pair[1]), int(getattr(pair[1], "id", 0) or 0)),
    )


def _find_entry_room():
    for obj in search_tag("darkhaven_academy_v01", category="siza_campaign_seed"):
        if str(getattr(obj.db, "room_id", "") or "") == ENTRY_ROOM_ID:
            return obj
    for obj in search_object(ENTRY_ROOM):
        if str(getattr(obj.db, "room_id", "") or "") == ENTRY_ROOM_ID:
            return obj
    return None


def _is_darkhaven_location(location):
    room_id = str(getattr(getattr(location, "db", None), "room_id", "") or "") if location else ""
    return room_id.startswith("DH7-ROOM-")


def _ensure_darkhaven_location(character, campaign_started=False):
    location = getattr(character, "location", None)
    if not campaign_started and _is_darkhaven_location(location):
        return location, False
    destination = _find_entry_room()
    if not destination:
        return location, False
    if location != destination:
        character.move_to(destination, quiet=True)
        return destination, True
    return destination, False


def _emit_darkhaven_opening(character):
    character.msg(
        "El portón de Darkhaven se cierra detrás de ti con un golpe demasiado parecido al de una celda. "
        "La lluvia corre por vitrales nuevos montados sobre piedra que claramente es más vieja que la idea de esta escuela."
    )
    character.msg(
        "Un muchacho flaco con una tablilla torcida espera bajo el arco. Dino comprueba tu nombre y hace una mueca. "
        "«Nereida. Bien. Trimago dijo que si llegabas por tu cuenta te mandara al patio. Squeek sabe dónde dejaron tu ingreso. "
        "Y no cruces ninguna puerta que diga Contención sólo porque esté abierta.»"
    )


def _emit_ready(session, status, **extra):
    packet = {"status": status, **extra}
    session.msg(siza_local_ready=((packet,), {}))


class CmdSizaLocalLogin(Command):
    """Open the single-player local world without exposing or storing account credentials."""

    key = "siza-local-login"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        session = self.caller
        if not _is_loopback(session):
            _emit_ready(session, "LOCAL_ACCESS_DENIED")
            return

        account, character = _find_player()
        if not account or not character:
            _emit_ready(session, "PERSISTENT_PLAYER_NOT_FOUND", character=LOCAL_CHARACTER)
            return

        session.sessionhandler.login(session, account)

        def finish_local_entry():
            try:
                current = account.get_puppet(session)
                if current and current != character:
                    account.unpuppet_object(session)
                    current = None
                if current != character:
                    account.puppet_object(session, character)
                account.db._last_puppet = character

                campaign = start_registered_campaign(character, LOCAL_CAMPAIGN, force=False)
                campaign_started = str(campaign.get("status") or "") == "STARTED"
                location, moved = _ensure_darkhaven_location(character, campaign_started=campaign_started)
                intro_pending = bool(getattr(character.db, "darkhaven_intro_pending", False))

                _emit_ready(
                    session,
                    "READY",
                    account=account.key,
                    character=LOCAL_CHARACTER,
                    puppet=character.key,
                    location=str(location or ""),
                    campaign=str(campaign.get("status") or ""),
                )
                if campaign_started or moved or intro_pending:
                    _emit_darkhaven_opening(character)
                    character.db.darkhaven_intro_pending = False
            except Exception as error:
                _emit_ready(session, "PUPPET_FAILED", character=character.key, error=str(error))

        reactor.callLater(0, finish_local_entry)
