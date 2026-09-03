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


def _find_character(name):
    wanted = str(name or LOCAL_CHARACTER).strip().lower()
    candidates = [obj for obj in search_object(name or LOCAL_CHARACTER) if str(obj.key).lower() == wanted]
    return sorted(candidates, key=lambda obj: int(getattr(obj, "id", 0) or 0))[0] if candidates else None


def _find_owner(character):
    accounts = list(AccountDB.objects.all().order_by("id"))
    for account in accounts:
        if character in list(utils.make_iter(account.characters)):
            return account
    for account in accounts:
        if bool(getattr(account, "is_superuser", False)) and character.access(account, "puppet"):
            return account
    return None


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

        character_name = str(self.args or "").strip() or LOCAL_CHARACTER
        character = _find_character(character_name)
        if not character:
            _emit_ready(session, "CHARACTER_NOT_FOUND", character=character_name)
            return

        account = _find_owner(character)
        if not account:
            _emit_ready(session, "ACCOUNT_NOT_FOUND", character=character.key)
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
                    character=character.key,
                    location=str(getattr(character, "location", "") or ""),
                )
            except Exception as error:
                _emit_ready(session, "PUPPET_FAILED", character=character.key, error=str(error))

        reactor.callLater(0, finish_local_entry)
