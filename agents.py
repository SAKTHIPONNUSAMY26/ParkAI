class ParkingAgent:
    def __init__(self, slots):
        self.slots = slots

    def get_status(self):
        return self.slots

    def recommend_slot(self):
        """Recommend the closest currently available slot to the entrance."""
        available_slots = [
            slot for slot in self.slots
            if slot["status"] == "Available"
        ]

        if not available_slots:
            return None

        # A lower configured distance is better. Slot ID is a stable tie-breaker.
        return min(
            available_slots,
            key=lambda slot: (slot.get("distance_from_entrance", float("inf")), slot["id"]),
        )

    def recommendation_reason(self, slot):
        """Explain the selected score using parking-layout data."""
        if slot is None:
            return None

        distance = slot.get("distance_from_entrance")
        if distance is None:
            return "Available slot selected using the configured parking order"

        return f"Nearest available slot (entrance distance score: {distance})"


class ManagementAgent:
    def __init__(self, slots):
        self.slots = slots

    def get_summary(self):
        total = len(self.slots)

        available = sum(1 for slot in self.slots if slot["status"] == "Available")
        occupied = sum(1 for slot in self.slots if slot["status"] == "Occupied")

        return {
            "total": total,
            "available": available,
            "occupied": occupied
        }


class AvailabilityAgent:
    def __init__(self, slots):
        self.slots = slots

    def get_available_slots(self):
        return [
            slot for slot in self.slots
            if slot["status"] == "Available"
        ]


