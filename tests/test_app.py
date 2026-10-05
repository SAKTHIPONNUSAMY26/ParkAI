import copy
import unittest

import app as park_app
from parking_data import parking_slots


class FakeDetector:
    def __init__(self):
        self.status = {
            "running": True, "detected": False, "vehicles": [], "error": None,
            "last_seen": None, "mode": "entrance", "occupied_slots": [],
        }

    def start(self):
        pass

    def stop(self, wait=True, manual=False):
        self.status.update(running=False, stopped=manual)

    def get_status(self):
        return dict(self.status)

    def set_mode(self, mode):
        if mode not in {"entrance", "slots"}:
            raise ValueError("Camera mode must be 'entrance' or 'slots'.")
        self.status.update(mode=mode, detected=False, vehicles=[], occupied_slots=[])


class ParkAITestCase(unittest.TestCase):
    def setUp(self):
        self.original_slots = copy.deepcopy(parking_slots)
        self.original_detector = park_app.vehicle_detector
        self.detector = FakeDetector()
        park_app.vehicle_detector = self.detector
        self.client = park_app.app.test_client()

    def tearDown(self):
        parking_slots[:] = self.original_slots
        park_app.vehicle_detector = self.original_detector

    def test_entrance_mode_recommends_nearest_available_slot(self):
        self.detector.status.update(detected=True, vehicles=["car"])
        data = self.client.get("/api/vehicle-status").get_json()
        self.assertEqual(data["mode"], "entrance")
        self.assertEqual(data["recommended_slot"], "A1")

    def test_slot_mode_marks_vehicle_roi_occupied_then_available(self):
        self.detector.status.update(mode="slots", occupied_slots=["A1"])
        self.client.get("/api/vehicle-status")
        self.assertEqual(next(slot for slot in parking_slots if slot["id"] == "A1")["status"], "Occupied")

        self.detector.status["occupied_slots"] = []
        self.client.get("/api/vehicle-status")
        self.assertEqual(next(slot for slot in parking_slots if slot["id"] == "A1")["status"], "Available")

    def test_occupied_slot_is_not_recommended_and_no_slot_is_handled(self):
        self.detector.status.update(detected=True, vehicles=["car"])
        next(slot for slot in parking_slots if slot["id"] == "A1")["status"] = "Occupied"
        self.assertEqual(self.client.get("/api/vehicle-status").get_json()["recommended_slot"], "A3")

        for slot in parking_slots:
            slot["status"] = "Occupied"
        self.assertIsNone(self.client.get("/api/vehicle-status").get_json()["recommended_slot"])

    def test_camera_failure_leaves_dashboard_available(self):
        self.detector.status.update(running=False, error="Could not open entrance camera 0.")
        response = self.client.get("/api/vehicle-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["error"], "Could not open entrance camera 0.")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_camera_mode_endpoint_switches_the_single_worker_mode(self):
        response = self.client.post("/api/camera-mode", json={"mode": "slots"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["mode"], "slots")
        self.assertEqual(self.detector.status["mode"], "slots")

    def test_camera_stop_endpoint_stops_only_the_camera_worker(self):
        response = self.client.post("/api/camera-stop")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["stopped"])
        self.assertFalse(self.detector.status["running"])

    def test_existing_park_and_exit_routes_remain_available(self):
        self.assertEqual(self.client.post("/park", data={"slot_id": "A1"}).status_code, 200)
        self.assertEqual(next(slot for slot in parking_slots if slot["id"] == "A1")["status"], "Occupied")
        self.assertEqual(self.client.post("/exit", data={"slot_id": "A1"}).status_code, 200)
        self.assertEqual(next(slot for slot in parking_slots if slot["id"] == "A1")["status"], "Available")


if __name__ == "__main__":
    unittest.main()
