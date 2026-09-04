from ipaddress import ip_address

from evennia import Command


LOCAL_LOGIN_BUILD = "0.12.0-local-autologin-disabled"


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


def _emit_ready(session, status, **extra):
    packet = {"status": status, **extra}
    session.msg(siza_local_ready=((packet,), {}))


class CmdSizaLocalLogin(Command):
    """Disabled legacy one-click local login.

    Character selection must happen explicitly through Evennia/login UI or a
    future Character Creator. This command intentionally never logs in or
    puppets a character.
    """

    key = "siza-local-login"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        session = self.caller
        if not _is_loopback(session):
            _emit_ready(session, "LOCAL_ACCESS_DENIED", build=LOCAL_LOGIN_BUILD)
            return

        _emit_ready(session, "LOCAL_LOGIN_DISABLED", build=LOCAL_LOGIN_BUILD)
        try:
            session.msg(
                "Auto-login local desactivado. Use el login normal de Evennia "
                "o el selector de personaje."
            )
        except Exception:
            pass
