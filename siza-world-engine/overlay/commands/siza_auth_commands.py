"""Account and character flow for the SIZA webclient.

The commands emit OOB packets only. They never select, rename or reset an
existing character; a persistent character is entered only after its owner
explicitly chooses it in the webclient.
"""

from __future__ import annotations

import base64
import json
import re

from evennia import Command, search_object
from evennia.accounts.models import AccountDB
from twisted.internet import reactor

from services.dm_campaign_registry import start_registered_campaign


AUTH_BUILD = "20260904-login-rebuild"
CHARACTER_TYPECLASS = "typeclasses.characters.Character"
START_ROOM_KEY = "Pescaderia de Darsena"
START_ROOM_ID = "CAR-KAL-DAR-007"
MAX_CHARACTER_NAME_LENGTH = 40
CHARACTER_NAME_PATTERN = re.compile(r"^[^#=,;|/\\\\<>]{3,40}$")


def _client_host(session):
    address = getattr(session, "address", "")
    if isinstance(address, (tuple, list)) and address:
        return str(address[0] or "").strip()
    return str(address or "").split(",", 1)[0].strip()


def _emit(session, status, **extra):
    session.msg(siza_auth=(({"status": status, "build": AUTH_BUILD, **extra},), {}))


def _session_for(command, account=None):
    session = getattr(command, "session", None)
    if session:
        return session
    sessions = list(getattr(getattr(account, "sessions", None), "all", lambda: [])())
    return sessions[0] if sessions else None


def _account_for(command):
    account = getattr(command, "account", None) or getattr(command, "caller", None)
    return account if getattr(account, "characters", None) is not None else None


def _decode_payload(raw):
    token = str(raw or "").strip()
    if not token:
        raise ValueError("Faltan datos del formulario.")
    padding = "=" * (-len(token) % 4)
    decoded = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Datos de formulario inválidos.")
    return payload


def _text(payload, key, maximum=120):
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError("Datos de formulario inválidos.")
    return value.strip()[:maximum]


def _valid_character_name(character_name):
    if not CHARACTER_NAME_PATTERN.match(character_name):
        return False, "Usa entre 3 y 40 caracteres; no uses #, =, comas ni barras."
    if len(character_name) > MAX_CHARACTER_NAME_LENGTH:
        return False, "El nombre es demasiado largo."
    for obj in search_object(character_name):
        if str(getattr(obj, "key", "")).casefold() == character_name.casefold():
            return False, "Ese nombre ya está en uso."
    return True, ""


def _start_room():
    rooms = [
        obj
        for obj in search_object(START_ROOM_KEY)
        if str(getattr(getattr(obj, "db", None), "room_id", "") or "") == START_ROOM_ID
    ]
    if not rooms:
        return None
    return sorted(rooms, key=lambda obj: int(getattr(obj, "id", 0) or 0))[0]


def _characters_for(account):
    characters = []
    for character in list(account.characters.all()):
        if character and character.access(account, "puppet"):
            characters.append(character)
    return sorted(characters, key=lambda character: (str(character.key).casefold(), int(character.id or 0)))


def _character_packet(character):
    return {
        "id": int(character.id),
        "name": str(character.key),
        "location": str(getattr(getattr(character, "location", None), "key", "") or ""),
    }


def _send_character_list(session, account):
    _emit(
        session,
        "CHARACTERS",
        account=str(account.key),
        characters=[_character_packet(character) for character in _characters_for(account)],
        slots=getattr(account, "get_available_character_slots", lambda: 0)(),
    )


def _create_character(account, session, character_name, profile):
    valid, error = _valid_character_name(character_name)
    if not valid:
        return None, error
    start_room = _start_room()
    if not start_room:
        return None, "El punto inicial de SIZA no está disponible todavía."
    character, errors = account.create_character(
        key=character_name,
        typeclass=CHARACTER_TYPECLASS,
        location=start_room,
        home=start_room,
        ip=_client_host(session),
    )
    if not character:
        return None, " ".join(str(item) for item in (errors or ["No se pudo crear el personaje."]))
    character.db.siza_character_profile = profile
    return character, ""


def _enter_character(session, account, character):
    def finish_entry():
        try:
            current = account.get_puppet(session)
            if current and current != character:
                account.unpuppet_object(session)
            if account.get_puppet(session) != character:
                account.puppet_object(session, character)
            campaign_state = start_registered_campaign(
                character, "CAMPAIGN-FARO-AHOGADO-VS01", force=False
            )
            _emit(
                session,
                "PUPPET_READY",
                account=str(account.key),
                character=str(character.key),
                location=str(getattr(getattr(character, "location", None), "key", "") or ""),
                campaign=str(campaign_state.get("status") or ""),
            )
        except Exception as error:
            _emit(session, "ERROR", message="No se pudo abrir ese personaje: %s" % error)

    reactor.callLater(0, finish_entry)


class CmdSizaAuthRegister(Command):
    """Create one account and its explicitly named first character."""

    key = "siza-auth-register"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        session = self.caller
        try:
            payload = _decode_payload(self.args)
            account_name = _text(payload, "account", 80)
            password = _text(payload, "password", 512)
            character_name = _text(payload, "character", MAX_CHARACTER_NAME_LENGTH)
            profile = {"origin": _text(payload, "origin", 80)}
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            _emit(session, "ERROR", message=str(error))
            return

        valid, error = _valid_character_name(character_name)
        if not valid:
            _emit(session, "ERROR", message=error)
            return
        if not _start_room():
            _emit(session, "ERROR", message="El punto inicial de SIZA no está disponible todavía.")
            return

        account, errors = AccountDB.create(
            username=account_name,
            password=password,
            ip=_client_host(session),
        )
        if not account or errors:
            _emit(session, "ERROR", message=" ".join(str(item) for item in (errors or ["No se pudo crear la cuenta."])))
            return

        session.sessionhandler.login(session, account)

        def finish_registration():
            character, creation_error = _create_character(account, session, character_name, profile)
            if not character:
                _emit(session, "ERROR", message=creation_error)
                return
            _enter_character(session, account, character)

        reactor.callLater(0, finish_registration)


class CmdSizaAuthCharacters(Command):
    """List only persistent characters owned by the current account."""

    key = "siza-auth-characters"
    locks = "cmd:all()"

    def func(self):
        account = _account_for(self)
        session = _session_for(self, account)
        if not account or not session:
            return
        _send_character_list(session, account)


class CmdSizaAuthCreateCharacter(Command):
    """Create a character for the logged-in account from Creator data."""

    key = "siza-auth-create-character"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        account = _account_for(self)
        session = _session_for(self, account)
        if not account or not session:
            return
        try:
            payload = _decode_payload(self.args)
            character_name = _text(payload, "character", MAX_CHARACTER_NAME_LENGTH)
            profile = {"origin": _text(payload, "origin", 80)}
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            _emit(session, "ERROR", message=str(error))
            return
        character, error = _create_character(account, session, character_name, profile)
        if not character:
            _emit(session, "ERROR", message=error)
            return
        _enter_character(session, account, character)


class CmdSizaAuthPlay(Command):
    """Puppet an explicitly selected owned character."""

    key = "siza-auth-play"
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        account = _account_for(self)
        session = _session_for(self, account)
        if not account or not session:
            return
        try:
            character_id = int(str(self.args or "").strip())
        except (TypeError, ValueError):
            _emit(session, "ERROR", message="El personaje seleccionado no es válido.")
            return
        character = next(
            (candidate for candidate in _characters_for(account) if int(candidate.id) == character_id),
            None,
        )
        if not character:
            _emit(session, "ERROR", message="No tienes acceso a ese personaje.")
            return
        _enter_character(session, account, character)
