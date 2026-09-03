from ipaddress import ip_address

from evennia import Command, search_object
from evennia.accounts.models import AccountDB
from evennia.utils import utils
from twisted.internet import reactor

from services.dm_campaign_registry import start_registered_campaign


LOCAL_CHARACTER = "Nereida"
LOCAL_CAMPAIGN = "CAMPAIGN-FARO-AHOGADO-VS01"
PILOT_ROOM = "Pescaderia de Darsena"
PILOT_ROOM_ID = "CAR-KAL-DAR-007"


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
    room_key = str(getattr(location, "key", "") or "").lower()

    if campaign:
        score += 200
        progressed = bool(campaign.get("completed_beats")) or int(campaign.get("director_turn", 0) or 0) > 0
        progressed = progressed or str(campaign.get("active_beat_id") or "") not in {"", "FA-BEAT-LEAD"}
        if progressed:
            score += 1200
    if room_id == "CAR-KAL-DAR-007" or "pescaderia" in room_key or "pescadería" in room_key:
        score += 900
    elif location:
        score += 100
    if str(getattr(character, "key", "") or "").lower() == LOCAL_CHARACTER.lower():
        score += 50
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


def _ensure_pilot_location(character):
    location = getattr(character, "location", None)
    if location and str(getattr(location, "key", "") or "").strip().lower() != "limbo":
        return location
    rooms = [
        obj
        for obj in search_object(PILOT_ROOM)
        if str(getattr(obj.db, "room_id", "") or "") == PILOT_ROOM_ID
    ]
    if not rooms:
        return location
    destination = sorted(rooms, key=lambda obj: int(getattr(obj, "id", 0) or 0))[0]
    character.move_to(destination, quiet=True)
    return destination


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
                location = _ensure_pilot_location(character)
                campaign = start_registered_campaign(character, LOCAL_CAMPAIGN, force=False)
                _emit_ready(
                    session,
                    "READY",
                    account=account.key,
                    character=LOCAL_CHARACTER,
                    puppet=character.key,
                    location=str(location or ""),
                    campaign=str(campaign.get("status") or ""),
                )
            except Exception as error:
                _emit_ready(session, "PUPPET_FAILED", character=character.key, error=str(error))

        reactor.callLater(0, finish_local_entry)
