from twisted.internet.defer import DeferredLock


_LOCKS = {}


def _character_key(character):
    dbid = getattr(character, "id", None)
    return dbid if dbid is not None else id(character)


def run_serialized(character, callable_obj, *args, **kwargs):
    """Run one narration job at a time for each character, preserving action order."""
    key = _character_key(character)
    lock = _LOCKS.get(key)
    if lock is None:
        lock = DeferredLock()
        _LOCKS[key] = lock
    return lock.run(callable_obj, *args, **kwargs)
