import sys
import threading
import types
import unittest
from unittest.mock import patch

import numpy as np

import app as park_app
import vehicle_detection
from vehicle_detection import VehicleDetector


class BlockingCapture:
    def __init__(self):
        self.read_started = threading.Event()
        self.released = threading.Event()
        self.release_calls = 0

    def read(self):
        self.read_started.set()
        self.released.wait(2)
        return False, None

    def release(self):
        self.release_calls += 1
        self.released.set()


class FrameCapture(BlockingCapture):
    def read(self):
        self.read_started.set()
        return True, np.zeros((24, 24, 3), dtype=np.uint8)


class EmptyResult:
    boxes = []


class FakeYOLO:
    def __init__(self, _model_path):
        pass

    def __call__(self, *_args, **_kwargs):
        return [EmptyResult()]


class StopRecorder:
    def __init__(self):
        self.calls = []

    def stop(self, wait=True):
        self.calls.append(wait)


class CameraLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fake_ultralytics = types.SimpleNamespace(YOLO=FakeYOLO)
        self.ultralytics = patch.dict(sys.modules, {"ultralytics": self.fake_ultralytics})
        self.ultralytics.start()

    def tearDown(self):
        self.ultralytics.stop()

    def _start_with(self, detector, capture):
        with patch.object(detector, "_open_camera", return_value=capture):
            detector.start()
            self.assertTrue(capture.read_started.wait(1), "camera worker did not begin reading")
            return detector._thread

    def test_stop_releases_entrance_and_slot_cameras(self):
        for mode in ("entrance", "slots"):
            with self.subTest(mode=mode):
                detector = VehicleDetector()
                if mode == "slots":
                    detector.set_mode(mode)
                capture = BlockingCapture()
                thread = self._start_with(detector, capture)
                detector.stop()
                self.assertFalse(thread.is_alive())
                self.assertTrue(capture.released.is_set())
                self.assertEqual(capture.release_calls, 1)

    def test_switch_releases_old_camera_before_starting_new_mode(self):
        detector = VehicleDetector()
        entrance_capture = BlockingCapture()
        slot_capture = BlockingCapture()
        with patch.object(detector, "_open_camera", side_effect=[entrance_capture, slot_capture]):
            detector.start()
            self.assertTrue(entrance_capture.read_started.wait(1))
            detector.set_mode("slots")
            self.assertTrue(entrance_capture.released.is_set())
            self.assertEqual(entrance_capture.release_calls, 1)

            detector.start()
            self.assertTrue(slot_capture.read_started.wait(1))
            detector.stop()
            self.assertTrue(slot_capture.released.is_set())
            self.assertEqual(slot_capture.release_calls, 1)

    def test_q_stops_preview_worker_and_releases_camera(self):
        detector = VehicleDetector(show_window=True)
        capture = FrameCapture()
        with (
            patch.object(detector, "_open_camera", return_value=capture),
            patch.object(vehicle_detection.cv2, "imshow"),
            patch.object(vehicle_detection.cv2, "waitKey", return_value=ord("q")),
            patch.object(vehicle_detection.cv2, "destroyAllWindows"),
        ):
            detector.start()
            detector._thread.join(timeout=2)
            self.assertFalse(detector._thread.is_alive())
            self.assertTrue(capture.released.is_set())
            self.assertEqual(capture.release_calls, 1)

    def test_flask_shutdown_hook_stops_active_detector(self):
        original_detector = park_app.vehicle_detector
        recorder = StopRecorder()
        try:
            park_app.vehicle_detector = recorder
            park_app.shutdown_camera_worker()
        finally:
            park_app.vehicle_detector = original_detector
        self.assertEqual(recorder.calls, [True])


if __name__ == "__main__":
    unittest.main()
