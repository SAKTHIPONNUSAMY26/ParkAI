parking_slots = [
    # Distance scores model this demo parking layout from the entrance.
    # Lower values mean a slot is closer and should be recommended first.
    {"id": "A1", "status": "Available", "distance_from_entrance": 1},
    {"id": "A2", "status": "Occupied", "distance_from_entrance": 2},
    {"id": "A3", "status": "Available", "distance_from_entrance": 3},
    {"id": "A4", "status": "Occupied", "distance_from_entrance": 4},
    {"id": "A5", "status": "Available", "distance_from_entrance": 5},
    {"id": "B1", "status": "Available", "distance_from_entrance": 6},
    {"id": "B2", "status": "Occupied", "distance_from_entrance": 7},
    {"id": "B3", "status": "Available", "distance_from_entrance": 8},
    {"id": "B4", "status": "Available", "distance_from_entrance": 9},
    {"id": "B5", "status": "Occupied", "distance_from_entrance": 10},
]

# Parking-camera regions of interest (ROIs), keyed by slot ID.
# Coordinates are normalized to the camera frame: (left, top, width, height),
# where 0.0 is the left/top edge and 1.0 is the right/bottom edge.  This makes
# the layout independent of webcam resolution.  Calibrate these values after
# positioning the webcam to view the parking area; add another entry for each
# new visible slot.  The example grid is a starting point for a demo view.
slot_rois = {
    "A1": (0.02, 0.05, 0.18, 0.35),
    "A2": (0.21, 0.05, 0.18, 0.35),
    "A3": (0.40, 0.05, 0.18, 0.35),
    "A4": (0.59, 0.05, 0.18, 0.35),
    "A5": (0.78, 0.05, 0.18, 0.35),
    "B1": (0.02, 0.55, 0.18, 0.35),
    "B2": (0.21, 0.55, 0.18, 0.35),
    "B3": (0.40, 0.55, 0.18, 0.35),
    "B4": (0.59, 0.55, 0.18, 0.35),
    "B5": (0.78, 0.55, 0.18, 0.35),
}
