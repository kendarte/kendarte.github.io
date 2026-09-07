# PLAYER transform authority

The character owns `pokerol_player_visual_state` (x, y, scale, revision).
Saving without ANCLAR is global. Rooms never select or store the PLAYER transform.
The persistent Evennia database remains `/data/evennia.db3`; no database maintenance
or character reset is part of this change. Sprite attributes and assets are unchanged.

## Root cause and writer audit

- `pokerol_ui_runtime_commands._player_metadata` previously preferred the character's
  per-Room map, then accepted the last visual save only in its original Room or
  with ANCLAR. This sent other coordinates or DEFAULT on ordinary travel.
- `pokerol_player_editor_v01.js` wrote that snapshot to the avatar and explicitly
  accepted lower revisions across Rooms. It now checks a character-global revision,
  separates character identities, and ignores incomplete snapshots.
- `pokerol_playable_client_v01.js` rebuilds backgrounds, exits, actor and action
  layers, not the avatar. It hands the completed snapshot to the PLAYER renderer.
- `pokerol_room_transition_v01.js` changes the stage class and signals completion;
  the editor renders its current state again at that boundary.
- `pokerol_scene_persistence_guard_v01.js` does not write PLAYER transforms.
- `pokerol_visual_recovery_v01.js` does not write PLAYER transforms.
- `pokerol_console_frame_v01.js` wraps the stage; its CSS and frame-shell CSS specify
  different avatar sizes. The editor now uses the original 96 x 140 logical base
  multiplied by scale, independent of frame initialization and viewport CSS.
- `pokerol_project_persistence_v01.js`, onboarding and trainer sprite editing manage
  image sources/fit, not avatar coordinates. Their sprite persistence is unchanged.
- The unloaded `pokerol_player_restore_v01.js` still contained a competing fallback
  style writer and timed restores. It is now only a delegate to the editor API.
- CSS avatar editing classes, pseudo-element shadows and transition animation were
  inspected. Inline important transform/size properties belong only to the editor.

Existing character-owned legacy maps migrate once using their highest revision.
Shared Room layouts are ignored because their author cannot be attributed safely.
Once visual_state exists neither legacy maps nor ANCLAR can override it.
A replaced avatar is rebound by the editor's child-list observer; no polling or
second restoration state is introduced.

## Automated regression checks

Run from the repository root:

```
python -B pokerol/overlay/tests/test_pokerol_player_visual_state.py
node pokerol/overlay/tests/test_pokerol_player_visual_state.js
```

Python executes the actual command and serializer definitions with isolated
Evennia dependencies. It covers saving, three Rooms and return, serialization into
another session object, two characters, conflicting legacy/anchor state, migration,
revision monotonicity, save identity validation and unchanged sprite references.
Node executes the real editor with a minimal DOM/emitter and covers save/ACK/close,
three Rooms, stale and incomplete packets, avatar replacement, fresh client state,
character switching and mismatched acknowledgements.
These tests do not substitute for authenticated production browser travel and login.
