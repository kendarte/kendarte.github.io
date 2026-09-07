"""Regression tests for character-owned transforms; no live DB is opened."""
import ast
import base64
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_definitions(filename):
    # Run the actual command/serializer definitions without booting Evennia.
    # External game systems are irrelevant to this focused persistence contract.
    tree = ast.parse((ROOT / 'commands' / filename).read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    ns = dict(Command=object, base64=base64, json=json,
              logger=SimpleNamespace(log_info=lambda msg: None), PLAYER_ANCHOR_BUILD='test')
    exec(compile(tree, filename, 'exec'), ns)
    return ns


class PlayerVisualStateTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_definitions('pokerol_ui_runtime_commands.py')
        self.commands = load_definitions('pokerol_player_anchor_commands.py')
        self.commands['_refresh'] = lambda caller: None
        self.rooms = [SimpleNamespace(id=i, db=SimpleNamespace(room_id='ROOM_'+str(i),
                      pokerol_player_layout={'x': 1, 'y': 2, 'scale': .35})) for i in (101, 102, 103)]
        self.a = self.actor(1)
        self.b = self.actor(2)

    def actor(self, ident):
        actor = SimpleNamespace(id=ident, key='Trainer'+str(ident), db=SimpleNamespace(),
                                location=self.rooms[0], packets=[])
        actor.msg = lambda **packet: actor.packets.append(packet)
        return actor

    def save(self, actor, x=63.4, y=118, scale=1.72, **extra):
        cmd = self.commands['CmdPokerolEditorPlayerState']()
        cmd.caller = actor
        cmd.args = base64.urlsafe_b64encode(json.dumps(dict(x=x, y=y, scale=scale,
                            anchored=False, seq=1, **extra)).encode()).decode()
        cmd.func()

    def transform(self, actor, room):
        packet = self.runtime['_player_metadata'](actor, room)
        return tuple(packet[k] for k in ('scene_x', 'scene_y', 'scene_scale')), packet

    def test_save_travels_three_rooms_and_survives_new_session(self):
        self.save(self.a)
        for room in self.rooms + self.rooms[:1]:
            self.a.location = room
            xyz, row = self.transform(self.a, room)
            self.assertEqual(xyz, (63.4, 118, 1.72))
            self.assertEqual(row['layout_source'], 'PLAYER_VISUAL_STATE')
            self.assertFalse(row['anchored'])
            self.assertEqual(row['revision'], 1)
        reloaded = self.actor(1)
        reloaded.db = SimpleNamespace(**json.loads(json.dumps(vars(self.a.db))))
        self.assertEqual(self.transform(reloaded, self.rooms[2])[0], (63.4, 118, 1.72))

    def test_visual_wins_over_room_maps_and_anchor(self):
        self.save(self.a)
        self.a.db.pokerol_player_anchor_enabled = True
        self.a.db.pokerol_player_anchor_layout = dict(x=3, y=4, scale=.5, revision=90)
        self.a.db.pokerol_player_room_layouts = {'102': dict(x=9, y=9, scale=.6)}
        self.a.db.pokerol_player_visual_state.update(room_dbref=101, anchored=False)
        self.assertEqual(self.transform(self.a, self.rooms[1])[0], (63.4, 118, 1.72))

    def test_two_trainers_never_share_transform(self):
        self.save(self.a)
        self.save(self.b, 27.8, 156, .83)
        for room in self.rooms:
            self.assertEqual(self.transform(self.a, room)[0], (63.4, 118, 1.72))
            self.assertEqual(self.transform(self.b, room)[0], (27.8, 156, .83))
            self.assertEqual(self.transform(self.b, room)[1]['character_dbref'], 2)

    def test_new_character_ignores_shared_room(self):
        for room in self.rooms:
            xyz, row = self.transform(self.a, room)
            self.assertEqual(xyz, (11, 94, 1))
            self.assertEqual(row['layout_source'], 'DEFAULT')

    def test_legacy_character_history_migrates_once_using_latest_revision(self):
        self.a.db.pokerol_player_room_layouts = {'101': dict(x=7, y=8, scale=.5, revision=2),
                                             '102': dict(x=63.4, y=118, scale=1.72, revision=7)}
        for room in self.rooms:
            self.assertEqual(self.transform(self.a, room)[0], (63.4, 118, 1.72))
        self.a.db.pokerol_player_room_layouts['103'] = dict(x=1, revision=99)
        self.assertEqual(self.transform(self.a, self.rooms[2])[0], (63.4, 118, 1.72))
        self.save(self.a)
        self.assertEqual(self.a.db.pokerol_player_visual_state['revision'], 8)

    def test_save_does_not_write_room_or_per_room_map(self):
        before = copy.deepcopy(vars(self.rooms[0].db))
        self.save(self.a)
        self.assertEqual(vars(self.rooms[0].db), before)
        self.assertFalse(hasattr(self.a.db, 'pokerol_player_room_layouts'))
        self.assertNotIn('room_dbref', self.a.db.pokerol_player_visual_state)
        ack = self.a.packets[-1]['pokerol_asset_result'][0][0]
        self.assertEqual(ack['character_dbref'], 1)
        self.assertEqual(ack['scope'], 'PLAYER_VISUAL_STATE')

    def test_save_for_previous_character_is_rejected(self):
        self.save(self.a, character_dbref=2)
        self.assertFalse(hasattr(self.a.db, 'pokerol_player_visual_state'))
        self.assertEqual(self.a.packets[-1]['pokerol_asset_result'][0][0]['status'], 'ERROR')

    def test_sprite_is_unchanged(self):
        self.a.db.scene_sprite = '/pokerol-assets/existing-female.png'
        self.save(self.a)
        for room in self.rooms:
            self.assertEqual(self.transform(self.a, room)[1]['scene_sprite'], self.a.db.scene_sprite)


if __name__ == '__main__':
    unittest.main()
