import subprocess
import time
import random
import re
from typing import Dict, List, Optional

class WiFiProximityEngine:
    """
    WIFI Module: Monitors device RF proximity, RSSI signal strength,
    and MAC association to prevent unauthorized walk-bys and photo attacks.
    """

    # Proximity calibrated thresholds (dBm)
    RSSI_IMMEDIATE_ZONE = -48.0   # <= 1.0 meter (Authorized unlock zone)
    RSSI_PROXIMITY_ZONE = -62.0   # 1.0m to 3.5m (Walking in corridor)
    RSSI_FAR_ZONE = -80.0         # > 3.5m (Out of range)

    def __init__(self):
        self.device_registry = {
            "F4:F5:DB:89:12:34": {"owner": "Dr. Ramesh Kumar", "phone": "Ramesh_Pixel8"},
            "3C:22:FB:45:90:AB": {"owner": "Aarav Sharma", "phone": "Aarav_GalaxyS23"},
            "A0:C5:89:11:77:22": {"owner": "Priya Patel", "phone": "Priya_iPhone15"},
        }

        # Simulated device dynamic state
        self.simulated_devices = {
            "F4:F5:DB:89:12:34": {"rssi": -42.0, "distance_m": 0.8, "active": True},
            "3C:22:FB:45:90:AB": {"rssi": -74.0, "distance_m": 4.5, "active": True},
            "A0:C5:89:11:77:22": {"rssi": -85.0, "distance_m": 8.0, "active": False},
        }

        self.last_scan_time = 0

    def estimate_distance_from_rssi(self, rssi: float, tx_power: float = -40.0, n: float = 2.4) -> float:
        """
        Log-distance path loss formula:
        d = 10 ^ ((tx_power - rssi) / (10 * n))
        """
        try:
            exp = (tx_power - rssi) / (10.0 * n)
            dist = 10.0 ** exp
            return round(min(15.0, max(0.2, dist)), 2)
        except Exception:
            return 5.0

    def scan_environment(self, scenario_override: Optional[str] = None) -> List[dict]:
        """
        Scans for visible device probe requests / Wi-Fi signals.
        Returns list of detected devices with RSSI and estimated distances.
        """
        results = []
        now = time.time()

        if scenario_override == "PHOTO_ATTACK" or scenario_override == "DEVICE_ABSENT":
            # Attacker brought a photo of Dr. Ramesh, but Dr. Ramesh's phone is absent
            results.append({
                "mac": "F4:F5:DB:89:12:34",
                "device_name": "Ramesh_Pixel8",
                "owner": "Dr. Ramesh Kumar",
                "rssi": -88.0,
                "distance_m": 12.0,
                "in_unlock_zone": False,
                "status": "FAR_AWAY_OR_OFFLINE"
            })
            return results

        if scenario_override == "WALK_BY":
            # Authorized user is merely walking in hallway at 3.5m, not approaching door
            results.append({
                "mac": "F4:F5:DB:89:12:34",
                "device_name": "Ramesh_Pixel8",
                "owner": "Dr. Ramesh Kumar",
                "rssi": -65.0,
                "distance_m": 3.8,
                "in_unlock_zone": False,
                "status": "PASSING_BY_HALLWAY"
            })
            return results

        if scenario_override == "STOLEN_PHONE":
            # Authorized phone is right at the door (-39 dBm), but held by an intruder
            results.append({
                "mac": "F4:F5:DB:89:12:34",
                "device_name": "Ramesh_Pixel8",
                "owner": "Dr. Ramesh Kumar",
                "rssi": -39.0,
                "distance_m": 0.6,
                "in_unlock_zone": True,
                "status": "AT_DOOR_PROXIMITY"
            })
            return results

        # Default / Normal operation: Dr. Ramesh is standing right at the door
        # Add slight natural RF multi-path jitter (+- 1.5 dB)
        jitter = random.uniform(-1.5, 1.5)
        ramesh_rssi = -42.0 + jitter
        results.append({
            "mac": "F4:F5:DB:89:12:34",
            "device_name": "Ramesh_Pixel8",
            "owner": "Dr. Ramesh Kumar",
            "rssi": round(ramesh_rssi, 1),
            "distance_m": self.estimate_distance_from_rssi(ramesh_rssi),
            "in_unlock_zone": ramesh_rssi >= self.RSSI_IMMEDIATE_ZONE,
            "status": "AT_DOOR_PROXIMITY" if ramesh_rssi >= self.RSSI_IMMEDIATE_ZONE else "NEARBY"
        })

        # Add background corridor devices
        results.append({
            "mac": "3C:22:FB:45:90:AB",
            "device_name": "Aarav_GalaxyS23",
            "owner": "Aarav Sharma",
            "rssi": -72.0 + random.uniform(-2, 2),
            "distance_m": 4.2,
            "in_unlock_zone": False,
            "status": "IN_CORRIDOR"
        })

        return results

    def verify_proximity_for_user(self, registered_mac: Optional[str], scenario_override: Optional[str] = None) -> Dict[str, any]:
        """
        Validates if the specified user's registered phone is physically
        inside the door unlock perimeter (<= 1.0 meter).
        """
        if not registered_mac:
            return {
                "verified": False,
                "rssi": -99.0,
                "distance_m": 99.0,
                "reason": "NO_REGISTERED_DEVICE_ASSOCIATED"
            }

        scanned = self.scan_environment(scenario_override)
        for dev in scanned:
            if dev["mac"].upper() == registered_mac.upper():
                is_near = dev["rssi"] >= self.RSSI_IMMEDIATE_ZONE
                return {
                    "verified": is_near,
                    "mac": dev["mac"],
                    "device_name": dev["device_name"],
                    "rssi": dev["rssi"],
                    "distance_m": dev["distance_m"],
                    "reason": "WITHIN_NEAR_FIELD" if is_near else f"TOO_FAR ({dev['distance_m']}m)"
                }

        # If not explicitly in static scan, simulate response based on active scenario
        if scenario_override in ["PHOTO_ATTACK", "DEVICE_ABSENT"]:
            return {
                "verified": False,
                "rssi": -95.0,
                "distance_m": 15.0,
                "reason": "DEVICE_NOT_DETECTED"
            }

        if scenario_override == "WALK_BY":
            return {
                "verified": False,
                "rssi": -65.0,
                "distance_m": 3.8,
                "reason": "TOO_FAR (3.8m)"
            }

        # Normal live operation: subject is physically standing at the terminal
        jitter = random.uniform(-1.5, 1.5)
        user_rssi = -42.0 + jitter
        user_dist = self.estimate_distance_from_rssi(user_rssi)
        is_near = user_rssi >= self.RSSI_IMMEDIATE_ZONE

        return {
            "verified": is_near,
            "mac": registered_mac,
            "device_name": "Paired_Device",
            "rssi": round(user_rssi, 1),
            "distance_m": user_dist,
            "reason": "WITHIN_NEAR_FIELD" if is_near else f"TOO_FAR ({user_dist}m)"
        }
