"""Tests for the data the dashboard card is built from."""
import sys
import unittest
from pathlib import Path

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "neosmartblinds"
sys.path.insert(0, str(COMPONENT_PATH))

from card_data import build_card_info  # noqa: E402


def _account():
    return {
        "entry_id": "entry1",
        "rooms": [
            {"room_id": "r2", "unique_id": "room_r2_c1", "room_name": "Office", "name": "Room: Office"},
            {"room_id": "r1", "unique_id": "room_r1_c1", "room_name": "dining", "name": "Room: dining"},
        ],
        "blinds": [
            {"unique_id": "c1_a-01", "blind_code": "a-01", "name": "Slider", "room_id": "r1", "has_percent": True},
            {"unique_id": "c1_b-01", "blind_code": "b-01", "name": None, "room_id": "r2", "has_percent": False},
        ],
        "schedules": [
            {"id": "s2", "room": "r1", "name": "dining Open at 9:00", "time": "9:00"},
            {"id": "s1", "room": "r1", "name": "dining Open at 7:00", "time": "7:00"},
            {"id": "s3", "room": "gone", "name": "Elsewhere", "time": "1:00"},
        ],
    }


def _lookup(domain, unique_id):
    return f"{domain}.{unique_id}".replace("-", "_")


class BuildCardInfoTest(unittest.TestCase):
    def test_rooms_are_sorted_by_name_ignoring_case(self):
        info = build_card_info([_account()], _lookup)
        self.assertEqual([r["name"] for r in info["rooms"]], ["dining", "Office"])

    def test_room_carries_its_entities(self):
        room = build_card_info([_account()], _lookup)["rooms"][0]
        self.assertEqual(room["id"], "entry1:r1")
        self.assertEqual(room["entity"], "cover.room_r1_c1")
        self.assertEqual(room["favorites"], ["button.room_r1_c1_fav_1", "button.room_r1_c1_fav_2"])

    def test_blinds_and_percent_support(self):
        room = build_card_info([_account()], _lookup)["rooms"][0]
        (blind,) = room["blinds"]
        self.assertEqual(blind["entity"], "cover.c1_a_01")
        self.assertTrue(blind["has_percent"])
        self.assertEqual(blind["favorites"], ["button.c1_a_01_fav_1", "button.c1_a_01_fav_2"])

    def test_blind_without_a_name_falls_back_to_its_code(self):
        office = build_card_info([_account()], _lookup)["rooms"][1]
        self.assertEqual(office["blinds"][0]["name"], "b-01")

    def test_schedules_belong_to_their_room_in_time_order(self):
        room = build_card_info([_account()], _lookup)["rooms"][0]
        self.assertEqual([s["entity"] for s in room["schedules"]], ["switch.s1", "switch.s2"])

    def test_schedule_for_unknown_room_is_dropped(self):
        info = build_card_info([_account()], _lookup)
        names = [s["name"] for r in info["rooms"] for s in r["schedules"]]
        self.assertNotIn("Elsewhere", names)

    def test_entities_missing_from_the_registry_are_skipped(self):
        def lookup(domain, unique_id):
            return None if domain == "switch" else _lookup(domain, unique_id)

        room = build_card_info([_account()], lookup)["rooms"][0]
        self.assertEqual(room["schedules"], [])
        self.assertEqual(len(room["blinds"]), 1)

    def test_two_accounts_with_the_same_room_id_stay_distinct(self):
        other = _account()
        other["entry_id"] = "entry2"
        ids = [r["id"] for r in build_card_info([_account(), other], _lookup)["rooms"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
