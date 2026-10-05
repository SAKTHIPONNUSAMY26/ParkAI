# ParkAI: Smart Parking Slot Recommendation and Occupancy Detection

## Problem Statement

ParkAI detects arriving vehicles at a parking entrance, checks current slot availability, and recommends a suitable free slot on a web dashboard.

## Camera Modes

ParkAI uses one webcam in one mode at a time. Switching modes stops and
releases the current camera worker before opening the selected mode, so the
demo never creates two streams from the same physical webcam.

### Entrance mode

```text
Car arrives
  -> Camera / vehicle image
  -> YOLO vehicle detection
  -> AvailabilityAgent checks available slots
  -> ParkingAgent selects the nearest available slot
  -> Dashboard displays the recommendation
```

Example: `Vehicle Detected: Car`, `Recommended Slot: A1`, `Reason: Nearest available slot`.

### Parking / Slot mode

```text
Webcam positioned to view parking slots
  -> YOLO detects vehicles
  -> Vehicle bounding-box centre is checked against each configured slot ROI
  -> Slot status becomes Occupied or Available
  -> Same dashboard grid and agents use the updated status
```

An occupied slot is therefore excluded from every recommendation; an empty
slot remains eligible.

## Technologies

- Python and Flask
- OpenCV and YOLO / Ultralytics
- HTML, CSS, and JavaScript

## Multi-Agent Architecture

- `AvailabilityAgent` returns slots whose status is `Available`.
- `ParkingAgent` selects the available slot with the lowest configured `distance_from_entrance` score and explains the choice.
- `ManagementAgent` provides total, available, and occupied counts.

## Features

- Real-time entrance vehicle and vehicle-type detection
- Configurable ROI-based parking-slot occupancy detection
- Entrance and parking-slot camera modes for one repositionable webcam
- Available-slot lookup and nearest-slot recommendation
- Automatic dashboard updates and annotated camera feed
- Parking-slot status grid
- Park Vehicle and Vehicle Exit actions to demonstrate status changes

## Install and Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

On its first detection attempt, Ultralytics downloads `yolo11n.pt` automatically if it is not already present.

## Project Structure

```text
ParkAI/
  app.py
  agents.py
  parking_data.py
  vehicle_detection.py
  requirements.txt
  README.md
  DEMO_GUIDE.md
  static/style.css
  templates/index.html
```

## Configuring Parking-Slot ROIs

`parking_data.py` contains `slot_rois`, a mapping from slot ID to
`(left, top, width, height)`. Values are normalized between `0.0` and `1.0`,
so they scale with the webcam frame resolution. Position the webcam to cover
the desired parking area, then calibrate each rectangle to that camera view:

```python
slot_rois = {
    "A1": (0.02, 0.05, 0.18, 0.35),
    "A2": (0.21, 0.05, 0.18, 0.35),
}
```

Only slots with an ROI are automatically updated in Parking / Slot mode.
Add a matching entry for each additional visible slot. The annotated feed
draws every ROI and its current Occupied/Available result to aid calibration.

## Demo and Real-World Coverage Limitation

- The entrance camera detects arriving vehicles.
- Slot occupancy detection needs camera visual coverage of each configured
  parking-slot region.
- The current demo uses one laptop webcam, repositioned between Entrance mode
  and Parking / Slot mode; it cannot view both areas at the same time.
- A real 200-slot car park needs additional camera coverage (and appropriately
  calibrated ROIs) for all slots. ParkAI does not claim that one webcam can
  monitor 200 slots simultaneously.

## Limitations and Future Work

- Slot state remains in memory and resets when Flask restarts.
- The entrance-distance scores should match the real parking layout.
- Future work may add individual slot cameras or sensors, persistent parking state, and remote dashboard access.
