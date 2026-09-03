from ipaddress import ip_address

from evennia import Command, search_object
from evennia.accounts.models import AccountDB
from evennia.utils import utils
from twisted.internet import reactor


LOCAL_CHARACTER = "Nereida"


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
        score += 1000
        if str(campaign.get("status") or "").upper() == "ACTIVE":
            score += 300
    if room_id == "CAR-KAL-DAR-007" or "pescaderia" in room_key or "pescadería" in room_key:
        score += 600
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
                _emit_ready(
                    session,
                    "READY",
                    account=account.key,
                    character=LOCAL_CHARACTER,
                    puppet=character.key,
                    location=str(getattr(character, "location", "") or ""),
                )
            except Exception as error:
                _emit_ready(session, "PUPPET_FAILED", character=character.key, error=str(error))

        reactor.callLater(0, finish_local_entry)
