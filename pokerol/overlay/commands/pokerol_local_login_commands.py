from ipaddress import ip_address
from evennia import Command

LOCAL_LOGIN_BUILD = "pokerol-0.2-unlogged-room-probe-safe"


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