"""One mode-switchable YOLO camera worker for ParkAI.

Only one mode owns the physical webcam at once: ``entrance`` detects arriving
vehicles and ``slots`` maps vehicles to configured parking-space ROIs.
"""

from __future__ import annotations

import threading
import time
import os
from pathlib import Path

import cv2


# Keep Ultralytics settings in the project so a restricted user profile does
# not prevent Flask from starting vehicle detection.
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(__file__).resolve().parent))


# COCO classes used by the small YOLO model: car, motorcycle, bus and truck.
VEHICLE_CLASS_IDS = [2, 3, 5, 7]
VEHICLE_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class VehicleDetector:
    """Runs one YOLO worker and exposes entrance or slot-occupancy results."""

    def __init__(self, camera_index: int = 0, slot_rois=None, show_window: bool = False):
        self.camera_index = camera_index
        self.slot_rois = slot_rois or {}
        self.show_window = show_window
        self._mode = "entrance"
        self._lock = threading.Lock()
        self._thread = None
        # The active capture is tracked separately from the worker so a stop
        # request can unblock a pending ``read`` as well as signal the loop.
        self._camera = None
        self._stop_event = threading.Event()
        self._manual_stop = False
        self._latest_frame = None
        self._retry_after = 0.0
        self._retry_delay = 2.0
        self._maximum_retry_delay = 30.0
        self._status = {
            "running": False,
            "detected": False,
            "vehicles": [],
            "error": None,
            "last_seen": None,
            "mode": "entrance",
            "occupied_slots": [],
        }

    def set_mode(self, mode: str):
        """Stop and release the camera before switching its single active mode."""
        if mode not in {"entrance", "slots"}:
            raise ValueError("Camera mode must be 'entrance' or 'slots'.")

        with self._lock:
            self._manual_stop = False
            if mode == self._mode:
                return
            self._mode = mode
        self.stop(wait=True)

        with self._lock:
            self._latest_frame = None
            self._status.update(
                running=False, detected=False, vehicles=[], error=None,
                last_seen=None, mode=mode, occupied_slots=[],
            )

    def start(self):
        """Start detection once, with backoff after camera/model failures."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self._manual_stop:
                return
            if time.monotonic() < self._retry_after:
                return

            self._stop_event.clear()
            self._status["running"] = True
            self._status["mode"] = self._mode
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self, wait: bool = True, manual: bool = False):
        """Stop the worker and release its capture (safe to call repeatedly)."""
        with self._lock:
            self._stop_event.set()
            if manual:
                self._manual_stop = True
            camera = self._camera
            thread = self._thread

        # Releasing here, rather than only in the worker's finally block,
        # unblocks camera.read() on backends that are waiting for a frame.
        self._release_camera(camera)

        if wait and thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)

        with self._lock:
            if not self._thread or not self._thread.is_alive():
                self._latest_frame = None
                self._status["running"] = False

    def _release_camera(self, camera=None):
        """Release one capture once; OpenCV release is intentionally idempotent."""
        with self._lock:
            if camera is None:
                target = self._camera
                self._camera = None
            elif camera is self._camera:
                target = camera
                self._camera = None
            else:
                # Another caller already released this capture.
                target = None

        if target is not None:
            try:
                target.release()
            except Exception:
                # Cleanup must not hide the original camera/model error.
                pass

    def get_status(self):
        with self._lock:
            status = dict(self._status)
            status["stopped"] = self._manual_stop
            return status

    def get_frame(self):
        """Return the latest annotated JPEG for the optional Flask video stream."""
        with self._lock:
            return self._latest_frame

    def _update_status(self, **changes):
        with self._lock:
            self._status.update(changes)

    def _schedule_retry(self, error):
        """Record a failure and delay the next automatic start attempt."""
        with self._lock:
            self._status.update(running=False, error=error)
            self._retry_after = time.monotonic() + self._retry_delay
            self._retry_delay = min(self._retry_delay * 2, self._maximum_retry_delay)

    def _reset_retry_delay(self):
        with self._lock:
            self._retry_after = 0.0
            self._retry_delay = 2.0

    def _open_camera(self):
        """Try the common Windows camera backends."""
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
            camera = cv2.VideoCapture(self.camera_index, backend)
            if camera.isOpened():
                return camera
            camera.release()
        return None

    def _roi_pixels(self, frame):
        """Convert normalized ROI config into integer frame coordinates."""
        height, width = frame.shape[:2]
        regions = {}
        for slot_id, (left, top, roi_width, roi_height) in self.slot_rois.items():
            x1, y1 = int(left * width), int(top * height)
            x2, y2 = int((left + roi_width) * width), int((top + roi_height) * height)
            regions[slot_id] = (x1, y1, x2, y2)
        return regions

    def _run(self):
        camera = None
        try:
            # Loading in the worker keeps Flask usable if YOLO fails to load.
            from ultralytics import YOLO

            with self._lock:
                mode = self._mode
            self._update_status(running=True, error=None, mode=mode)
            model = YOLO("yolo11n.pt")
            if self._stop_event.is_set():
                return
            camera = self._open_camera()

            with self._lock:
                self._camera = camera

            if camera is None:
                self._schedule_retry(
                    (
                        f"Could not open {mode} camera {self.camera_index}. "
                        "The parking dashboard remains available."
                    )
                )
                return

            if self._stop_event.is_set():
                return

            self._reset_retry_delay()

            while not self._stop_event.is_set():
                success, frame = camera.read()
                if not success:
                    self._update_status(error=f"Could not read a frame from the {mode} camera.")
                    time.sleep(0.2)
                    continue

                result = model(frame, classes=VEHICLE_CLASS_IDS, conf=0.5, verbose=False)[0]
                detected_ids = []
                vehicle_boxes = []

                for box in result.boxes:
                    class_id = int(box.cls[0])
                    detected_ids.append(class_id)
                    x1, y1, x2, y2 = (int(value) for value in box.xyxy[0])
                    label = VEHICLE_NAMES.get(class_id, "vehicle")
                    vehicle_boxes.append((x1, y1, x2, y2))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        label,
                        (x1, max(25, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )

                vehicle_names = sorted({VEHICLE_NAMES[item] for item in detected_ids})
                occupied_slots = []
                if mode == "slots":
                    for slot_id, (rx1, ry1, rx2, ry2) in self._roi_pixels(frame).items():
                        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 170, 0), 2)
                        # A vehicle occupies a slot when the centre of its YOLO box
                        # falls inside that slot's configured region.
                        occupied = any(
                            rx1 <= (x1 + x2) // 2 <= rx2 and ry1 <= (y1 + y2) // 2 <= ry2
                            for x1, y1, x2, y2 in vehicle_boxes
                        )
                        if occupied:
                            occupied_slots.append(slot_id)
                        label = f"{slot_id}: {'Occupied' if occupied else 'Available'}"
                        cv2.putText(frame, label, (rx1 + 4, max(20, ry1 + 22)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                    (0, 0, 255) if occupied else (0, 140, 0), 2)
                encoded, jpeg = cv2.imencode(".jpg", frame)
                if encoded:
                    with self._lock:
                        self._latest_frame = jpeg.tobytes()

                self._update_status(
                    running=True,
                    detected=bool(vehicle_names) if mode == "entrance" else bool(occupied_slots),
                    vehicles=vehicle_names,
                    error=None,
                    last_seen=time.strftime("%H:%M:%S") if vehicle_names else None,
                    mode=mode,
                    occupied_slots=occupied_slots,
                )

                # This preview is enabled only when the module runs directly.
                if self.show_window:
                    cv2.imshow(f"ParkAI {mode.title()} Camera - press Q to stop", frame)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        self.stop(manual=True)

        except Exception as error:
            self._schedule_retry(f"Vehicle detection error: {error}")
        finally:
            self._release_camera(camera)
            with self._lock:
                self._latest_frame = None
            if self.show_window:
                cv2.destroyAllWindows()
            self._update_status(running=False)


if __name__ == "__main__":
    detector = VehicleDetector(show_window=True)
    detector.start()
    try:
        while detector.get_status()["running"] or detector._thread.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        detector.stop()
