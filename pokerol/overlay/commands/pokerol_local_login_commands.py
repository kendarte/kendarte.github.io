from ipaddress import ip_address

from evennia import Command
from evennia.accounts.models import AccountDB

LOCAL_LOGIN_BUILD = "pokerol-0.3-auth-state"


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


def _command_session(command):
    session = getattr(command, "session", None)
    if session:
        return session

    caller = getattr(command, "caller", None)
    if caller and hasattr(caller, "get_account") and hasattr(caller, "get_puppet"):
        return caller

    sessions = getattr(caller, "sessions", None)
    if sessions:
        try:
            rows = sessions.all()
            if rows:
                return rows[0]
        except Exception:
            pass
    return None


def _command_account(command, session):
    account = getattr(command, "account", None)
    if account:
        return account

    caller = getattr(command, "caller", None)
    candidate = getattr(caller, "account", None)
    if candidate:
        return candidate

    if session:
        try:
            candidate = session.get_account()
            if candidate:
                return candidate
        except Exception:
            pass

        uid = getattr(session, "uid", None)
        if uid:
            try:
                return AccountDB.objects.get(id=uid)
            except AccountDB.DoesNotExist:
                pass
    return None


def _command_character(command, session):
    if session:
        try:
            puppet = session.get_puppet()
            if puppet:
                return puppet
        except Exception:
            pass

    caller = getattr(command, "caller", None)
    if caller and getattr(caller, "location", None) is not None:
        return caller
    return None


class CmdPokerolAuthState(Command):
    """Return authoritative authentication state to the visual client."""

    key = "pokerol-auth-state"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        session = _command_session(self)
        account = _command_account(self, session)
        character = _command_character(self, session)
        requested_name = str(self.args or "").strip()

        account_exists = False
        if requested_name:
            account_exists = AccountDB.objects.filter(username__iexact=requested_name).exists()

        packet = {
            "status": "AUTH_STATE",
            "build": LOCAL_LOGIN_BUILD,
            "logged_in": bool(account),
            "account_name": str(getattr(account, "key", "") or getattr(account, "username", "") or ""),
            "character_name": str(getattr(character, "key", "") or ""),
            "requested_name": requested_name,
            "account_exists": bool(account_exists),
        }

        target = session or getattr(self, "caller", None)
        if target:
            target.msg(pokerol_auth_state=((packet,), {}))


class CmdPokerolLocalLogin(Command):
    key = "pokerol-local-login"
    aliases = ["siza-local-login", "pokerol-room-state"]
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        session = self.caller

        # The visual client probes room state as soon as the transport opens.
        # Before authentication there is no Character/Room yet, so this must be
        # a silent no-op instead of surfacing an Evennia command error.
        if str(getattr(self, "cmdstring", "") or "").strip().lower() == "pokerol-room-state":
            return

        status = "LOCAL_LOGIN_DISABLED" if _is_loopback(session) else "LOCAL_ACCESS_DENIED"
        session.msg(pokerol_local_ready=(({"status": status, "build": LOCAL_LOGIN_BUILD},), {}))
        if status == "LOCAL_LOGIN_DISABLED":
            session.msg("Auto-login local desactivado. Usa la pantalla de acceso de POKEROL.")
