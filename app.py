import atexit
import time

from flask import Flask, Response, jsonify, render_template, request
from parking_data import parking_slots, slot_rois
from agents import AvailabilityAgent, ManagementAgent, ParkingAgent
from vehicle_detection import VehicleDetector

app = Flask(__name__)

# The detector runs separately from Flask. A camera or YOLO error therefore
# never prevents the existing dashboard, parking, or exit routes from working.
vehicle_detector = VehicleDetector(slot_rois=slot_rois)


def shutdown_camera_worker():
    """Release the webcam when the Flask process exits."""
    vehicle_detector.stop(wait=True)


atexit.register(shutdown_camera_worker)


def apply_slot_occupancy(detection):
    """Apply parking-camera observations to the same data used by the agents."""
    if detection["mode"] != "slots" or detection["error"] or not detection["running"]:
        return

    occupied_slots = set(detection["occupied_slots"])
    for slot in parking_slots:
        if slot["id"] in slot_rois:
            slot["status"] = "Occupied" if slot["id"] in occupied_slots else "Available"


def dashboard_context(displayed_slots=None, message=None):
    """Build the shared dashboard values without changing any route behavior."""
    summary = ManagementAgent(parking_slots).get_summary()
    return {
        "parking_slots": parking_slots if displayed_slots is None else displayed_slots,
        "total_slots": summary["total"],
        "available_slots": summary["available"],
        "occupied_slots": summary["occupied"],
        "message": message,
    }


@app.get("/api/vehicle-status")
def vehicle_status():
    """Return current camera-mode detection and entrance guidance when applicable."""
    vehicle_detector.start()
    detection = vehicle_detector.get_status()
    apply_slot_occupancy(detection)

    availability_agent = AvailabilityAgent(parking_slots)
    parking_agent = ParkingAgent(parking_slots)
    available_slots = availability_agent.get_available_slots()
    recommendation = (
        parking_agent.recommend_slot()
        if detection["mode"] == "entrance" and detection["detected"]
        else None
    )
    recommendation_reason = parking_agent.recommendation_reason(recommendation)

    return jsonify(
        running=detection["running"],
        detected=detection["detected"],
        vehicle_detected=detection["detected"],
        vehicles=detection["vehicles"],
        vehicle_type=detection["vehicles"][0] if detection["vehicles"] else None,
        error=detection["error"],
        last_seen=detection["last_seen"],
        mode=detection["mode"],
        occupied_slots=detection["occupied_slots"],
        stopped=detection.get("stopped", False),
        available_slots=[slot["id"] for slot in available_slots],
        recommended_slot=recommendation["id"] if recommendation else None,
        recommendation_status=recommendation["status"] if recommendation else None,
        recommendation_reason=recommendation_reason,
    )


@app.route("/api/camera-mode", methods=["GET", "POST"])
def camera_mode():
    """Select entrance or parking-slot mode; never opens two webcam streams."""
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        try:
            vehicle_detector.set_mode(payload.get("mode"))
        except ValueError as error:
            return jsonify(error=str(error)), 400

    vehicle_detector.start()
    detection = vehicle_detector.get_status()
    return jsonify(mode=detection["mode"], running=detection["running"], error=detection["error"])


@app.post("/api/camera-stop")
def stop_camera():
    """Stop the current preview worker without stopping the Flask server."""
    vehicle_detector.stop(manual=True)
    detection = vehicle_detector.get_status()
    return jsonify(mode=detection["mode"], running=detection["running"], stopped=True)


@app.get("/video-feed")
def video_feed():
    """Stream the single active mode's YOLO-annotated frames."""
    vehicle_detector.start()

    def generate_frames():
        while True:
            frame = vehicle_detector.get_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.08)

    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():
    return render_template("index.html", **dashboard_context())


# =========================
# FIND AVAILABLE PARKING
# =========================
@app.route("/available")
def available():

    available_slots_list = [
        slot for slot in parking_slots
        if slot["status"] == "Available"
    ]

    return render_template("index.html", **dashboard_context(available_slots_list))


# =========================
# PARK VEHICLE
# Available → Occupied
# =========================
@app.route("/park", methods=["POST"])
def park():

    slot_id = request.form.get("slot_id")

    message = ""

    for slot in parking_slots:

        if str(slot["id"]) == str(slot_id):

            if slot["status"] == "Available":

                slot["status"] = "Occupied"

                message = (
                    f"Vehicle parked successfully in Slot {slot_id}!"
                )

            else:

                message = (
                    f"Slot {slot_id} is not available."
                )

            break

    return render_template("index.html", **dashboard_context(message=message))


# =========================
# VEHICLE EXIT
# Occupied → Available
# =========================
@app.route("/exit", methods=["POST"])
def exit_vehicle():

    slot_id = request.form.get("slot_id")

    message = ""

    for slot in parking_slots:

        if str(slot["id"]) == str(slot_id):

            if slot["status"] == "Occupied":

                slot["status"] = "Available"

                message = (
                    f"Vehicle exited from Slot {slot_id} successfully!"
                )

            else:

                message = (
                    f"Slot {slot_id} is not occupied."
                )

            break

    return render_template("index.html", **dashboard_context(message=message))


# =========================
# RUN FLASK APPLICATION
# =========================
if __name__ == "__main__":
    try:
        app.run(debug=True)
    finally:
        shutdown_camera_worker()

