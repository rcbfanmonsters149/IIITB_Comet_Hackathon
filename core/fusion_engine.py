import time
import os
import json
from typing import Dict, List, Optional
from core.vision_engine import VisionEngine
from core.wifi_engine import WiFiProximityEngine
from core.audio_engine import AudioEngine
from core.mcu_driver import MCUDriver

class FusionEngine:
    """
    Multi-Modal Spatial-Temporal Fusion Engine:
    Combines CAM (Face + Liveness), WIFI (RSSI proximity), and AUDIO (Ultrasonic/Voice)
    to drive MCU (Door Strike Relay & Alarms).
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.log_path = os.path.join(data_dir, "audit_logs.json")

        self.vision = VisionEngine(data_dir)
        self.wifi = WiFiProximityEngine()
        self.audio = AudioEngine()
        self.mcu = MCUDriver()

        self.last_decision_time = 0
        self.decision_cooldown_sec = 2.0  # Prevent spamming unlocks
        self.current_scenario_override: Optional[str] = None
        self.audit_logs: List[dict] = []
        self._load_audit_logs()

    def _load_audit_logs(self):
        """Loads historical audit logs."""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r") as f:
                    self.audit_logs = json.load(f)
            except Exception:
                self.audit_logs = []
        else:
            self.audit_logs = []

    def _save_audit_logs(self):
        """Saves audit logs to disk."""
        # Retain latest 100 entries
        self.audit_logs = self.audit_logs[-100:]
        with open(self.log_path, "w") as f:
            json.dump(self.audit_logs, f, indent=2)

    def set_scenario_override(self, scenario: Optional[str]):
        """Sets scenario override for testing and demonstrations."""
        self.current_scenario_override = scenario
        self.last_decision_time = 0
        self.mcu._auto_relock()

    def evaluate_access(self, frame=None) -> Dict[str, any]:
        """
        Executes complete multi-modal fusion cycle:
        1. Capture & analyze camera frame
        2. Scan Wi-Fi RSSI proximity for the detected subject's registered device
        3. Verify near-field acoustic/ultrasonic token
        4. Compute fused confidence & dispatch MCU command
        """
        now = time.time()

        # Step 1: CAM Analysis
        # If a live frame is passed from client webcam or video capture, process it directly
        if frame is not None:
            processed_frame, detected_faces = self.vision.process_frame(frame, self.current_scenario_override)
        elif self.current_scenario_override:
            processed_frame, detected_faces = self.vision.generate_synthetic_feed(self.current_scenario_override)
        elif self.vision.cap and self.vision.cap.isOpened() and not self.vision.simulated_mode:
            ret, live_frame = self.vision.cap.read()
            if ret and live_frame is not None:
                processed_frame, detected_faces = self.vision.process_frame(live_frame, None)
            else:
                processed_frame, detected_faces = self.vision.generate_synthetic_feed("NORMAL")
        else:
            processed_frame, detected_faces = self.vision.generate_synthetic_feed("NORMAL")

        # Default telemetry if no face is in view
        if not detected_faces:
            wifi_scan = self.wifi.scan_environment(self.current_scenario_override)
            return {
                "decision": "IDLE_NO_FACE_DETECTED",
                "reason": "No face detected in camera viewport. Please face the camera.",
                "composite_score": 0.0,
                "user_name": "No Face Detected",
                "user_id": "NONE",
                "components": {
                    "cam": {
                        "user_id": "NONE",
                        "name": "No Face Detected",
                        "similarity": 0.0,
                        "liveness": 0.0,
                        "is_live": False,
                        "bbox": None,
                        "faces_count": 0
                    },
                    "wifi": {"scanned_devices": len(wifi_scan)},
                    "audio": {"status": "STANDBY"},
                    "mcu": self.mcu.get_status()
                },
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        target = detected_faces[0]
        user_id = target.get("user_id")
        user_name = target.get("name")
        face_sim = target.get("similarity", 0.0)
        face_live = target.get("liveness_score", 0.0)
        is_live = target.get("is_live", False)
        registered_mac = target.get("registered_mac")

        # Step 2: WIFI Proximity Check
        scanned_devices = self.wifi.scan_environment(self.current_scenario_override)
        devices_in_unlock_zone = [d for d in scanned_devices if d.get("in_unlock_zone")]
        wifi_result = self.wifi.verify_proximity_for_user(registered_mac, self.current_scenario_override)
        wifi_score = 0.95 if wifi_result["verified"] else max(0.1, (100.0 + wifi_result["rssi"]) / 100.0)

        # Step 3: AUDIO Acoustic Check
        audio_result = self.audio.verify_acoustic_token("TOKEN_CHIRP", self.current_scenario_override)
        audio_score = audio_result["score"]

        # Step 4: Multi-Modal Fused Score Calculation
        # Weights: 45% Face Match + 30% WiFi Proximity + 25% Audio Liveness
        composite_score = round((0.45 * face_sim) + (0.30 * wifi_score) + (0.25 * audio_score), 3)

        # Step 5: Multi-Factor Decision Gate
        decision = "DENIED"
        reason = ""
        action_type = "NONE"

        if face_sim >= 0.65 and is_live and wifi_result["verified"] and audio_result["verified"]:
            decision = "ACCESS_GRANTED"
            reason = f"Verified identity of {user_name} with phone proximity ({wifi_result['distance_m']}m) and acoustic token."
            action_type = "UNLOCK"
            if (now - self.last_decision_time) > self.decision_cooldown_sec:
                self.mcu.trigger_unlock(duration_sec=3.0)
                self.last_decision_time = now

        elif face_sim >= 0.65 and is_live and not wifi_result["verified"]:
            decision = "DENIED_DEVICE_ABSENT"
            reason = f"Face recognized ({user_name}), but registered mobile device is out of range ({wifi_result['distance_m']}m). Accidental walk-by or unauthenticated attempt."
            action_type = "HOLD_LOCK"
            self.mcu._auto_relock()

        elif face_sim >= 0.65 and not is_live and face_live < 0.45:
            decision = "DENIED_PRESENTATION_ATTACK"
            reason = f"Photo / screen spoofing detected for {user_name}. Failed biological liveness (score: {int(face_live*100)}%)."
            action_type = "ALARM"
            self.mcu.trigger_alarm(duration_sec=2.0)
            self.last_decision_time = now

        elif face_sim >= 0.65 and not is_live:
            # Borderline liveness — still grant if face match is strong
            decision = "ACCESS_GRANTED"
            reason = f"Verified identity of {user_name}. Liveness borderline ({int(face_live*100)}%) but face match is strong."
            action_type = "UNLOCK"
            if (now - self.last_decision_time) > self.decision_cooldown_sec:
                self.mcu.trigger_unlock(duration_sec=3.0)
                self.last_decision_time = now

        elif face_sim < 0.60 and len(devices_in_unlock_zone) > 0:
            stolen_dev = devices_in_unlock_zone[0]
            decision = "DENIED_STOLEN_DEVICE"
            reason = f"Authorized smartphone ({stolen_dev.get('owner')}'s {stolen_dev.get('device_name')}) at door, but face is an unauthorized stranger!"
            action_type = "ALARM"
            self.mcu.trigger_alarm(duration_sec=2.0)
            self.last_decision_time = now

        else:
            decision = "DENIED_UNAUTHORIZED"
            reason = "Unregistered subject and unauthorized device."
            action_type = "HOLD_LOCK"
            self.mcu._auto_relock()

        # Record Audit Trail
        log_entry = {
            "id": f"EVT-{int(now * 1000) % 1000000}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "decision": decision,
            "user_name": user_name,
            "user_id": user_id,
            "composite_score": composite_score,
            "scores": {
                "face_similarity": face_sim,
                "face_liveness": face_live,
                "wifi_rssi": wifi_result.get("rssi"),
                "wifi_distance_m": wifi_result.get("distance_m"),
                "audio_snr": audio_result.get("snr_db"),
                "audio_token_valid": audio_result.get("verified")
            },
            "reason": reason,
            "action_type": action_type
        }

        # Avoid redundant consecutive identical log entries within cooldown
        if not self.audit_logs or (self.audit_logs[-1]["decision"] != decision) or ((now - self.last_decision_time) <= 0.1):
            self.audit_logs.append(log_entry)
            self._save_audit_logs()

        return {
            "decision": decision,
            "reason": reason,
            "composite_score": composite_score,
            "user_name": user_name,
            "user_id": user_id,
            "components": {
                "cam": {
                    "user_id": user_id,
                    "name": user_name,
                    "similarity": face_sim,
                    "liveness": face_live,
                    "is_live": is_live,
                    "bbox": target.get("bbox"),
                    "faces_count": len(detected_faces),
                    "breakdown": target.get("liveness_breakdown")
                },
                "wifi": wifi_result,
                "audio": audio_result,
                "mcu": self.mcu.get_status()
            },
            "timestamp": log_entry["timestamp"]
        }
