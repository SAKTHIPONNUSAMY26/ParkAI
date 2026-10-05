# ParkAI Demo Guide

## Before the Demo

1. Connect or enable the webcam and close other apps using it.
2. Open PowerShell in the `ParkAI` folder.
3. Start the system:

   ```powershell
   python app.py
   ```

4. Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Demonstration Steps

1. Introduce ParkAI as a multi-agent smart parking system.
2. Point out the Total, Available, and Occupied slot cards.
3. Show the parking-slot grid and its colors: green Available and red Occupied.
4. Select **Entrance mode** and show the entrance-camera feed.
5. Place a car, model car, or clear car image in front of the webcam.
6. Show the YOLO bounding box and the `Vehicle Detected` status.
7. Point out `Vehicle Type`, the recommended parking slot, and its reason: nearest available entrance-distance score.
8. Explain that `AvailabilityAgent` finds available slots and `ParkingAgent` chooses the best one.
9. Reposition the same webcam to view the configured parking-slot layout and select **Parking / Slot mode**. The entrance stream is stopped before this mode uses the camera.
10. Show the ROI rectangles. Place a vehicle in A1's region: A1 becomes Occupied; remove it: A1 becomes Available.
11. Switch back to **Entrance mode** and show that an occupied A1 is not recommended, while an empty A1 can be recommended.
12. If needed, click **Park Vehicle** for an available slot and show it becoming red/Occupied.
13. Click **Vehicle Exit** and show the slot becoming green/Available again.

## Important Explanation for Staff

The entrance camera detects arriving vehicles. Parking / Slot mode uses the same
webcam only after it has been repositioned to view the configured slot ROIs.
It detects occupancy, not a vehicle owner or vehicle identity. One laptop
webcam is suitable for this small demonstration only; a real 200-slot area
requires additional camera coverage.

## If the Camera Feed Is Unavailable

1. Close Windows Camera, Teams, Zoom, or browser tabs using the webcam.
2. Check Windows camera privacy permissions.
3. Restart `python app.py`.
4. Confirm the correct camera index is configured in `VehicleDetector(camera_index=0)` if an external webcam uses another index.
