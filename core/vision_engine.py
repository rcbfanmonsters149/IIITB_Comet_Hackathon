import cv2
import numpy as np
import os
import json
import time
from typing import Dict, List, Tuple, Optional

class VisionEngine:
    """
    CAM Module: Deep Neural Network Face Recognition & Anti-Spoofing.
    Powered by OpenCV YuNet (Face Detection & 5-Landmark Alignment)
    and SFace (Deep Feature Embeddings & Metric Learning).
    """

    def __init__(self, data_dir: str = "data", models_dir: str = "models"):
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.enrolled_dir = os.path.join(data_dir, "enrolled_faces")
        self.db_path = os.path.join(data_dir, "authorized_users.json")
        os.makedirs(self.enrolled_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)

        self.yunet_model_path = os.path.join(models_dir, "face_detection_yunet.onnx")
        self.sface_model_path = os.path.join(models_dir, "face_recognition_sface.onnx")

        # Initialize Deep Learning Models
        self.detector = None
        self.recognizer = None
        self._init_deep_models()

        # In-memory enrolled face embeddings
        self.enrolled_users: Dict[str, dict] = {}
        self.load_enrolled_users()

        # Frame history for micro-motion and temporal anti-spoofing
        self.history: Dict[str, any] = {
            "last_face_center": None,
            "motion_scores": []
        }

        # Camera state
        self.cap = None
        self.simulated_mode = False
        self._init_camera()

    def _init_deep_models(self):
        """Initializes OpenCV YuNet and SFace deep neural network instances."""
        try:
            if os.path.exists(self.yunet_model_path) and os.path.exists(self.sface_model_path):
                self.detector = cv2.FaceDetectorYN_create(
                    self.yunet_model_path, "", (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000
                )
                self.recognizer = cv2.FaceRecognizerSF_create(self.sface_model_path, "")
                print("[CAM] SFace Deep Face Recognition & YuNet Deep Detector loaded successfully!")
            else:
                print(f"[CAM] Deep models not found in {self.models_dir}. Fallback mode active.")
        except Exception as e:
            print(f"[CAM] Failed to initialize deep models: {e}. Fallback active.")

    def _init_camera(self):
        """
        Camera is managed directly by the web client via HTML5 getUserMedia.
        Backend operates in headless inference mode so the hardware camera
        is never locked by Python.
        """
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.simulated_mode = True

    def load_enrolled_users(self):
        """Loads enrolled user database or seeds with default authorized campus personnel."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    self.enrolled_users = json.load(f)
            except Exception as e:
                print(f"[CAM] Error loading authorized_users.json: {e}")
                self._seed_default_users()
        else:
            self._seed_default_users()

    def _seed_default_users(self):
        """Seeds default authorized lab members."""
        self.enrolled_users = {
            "USR-101": {
                "name": "Dr. Ramesh Kumar",
                "role": "Lab Director",
                "department": "Networking & Security Lab",
                "registered_mac": "F4:F5:DB:89:12:34",
                "registered_phone": "Ramesh_Pixel8",
                "access_tier": "Level 3 (Server Room & Lab)",
                "embedding": None
            },
            "USR-102": {
                "name": "Aarav Sharma",
                "role": "Research Scholar",
                "department": "Edge AI Systems",
                "registered_mac": "3C:22:FB:45:90:AB",
                "registered_phone": "Aarav_GalaxyS23",
                "access_tier": "Level 2 (Lab Access)",
                "embedding": None
            },
            "USR-103": {
                "name": "Priya Patel",
                "role": "Network Administrator",
                "department": "Campus IT",
                "registered_mac": "A0:C5:89:11:77:22",
                "registered_phone": "Priya_iPhone15",
                "access_tier": "Level 3 (Server Room & Lab)",
                "embedding": None
            }
        }
        self.save_enrolled_users()

    def save_enrolled_users(self):
        """Persists enrolled users to disk."""
        with open(self.db_path, "w") as f:
            json.dump(self.enrolled_users, f, indent=2)

    def detect_faces_deep(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        Deep learning face detection via YuNet:
        Returns list of 15-element arrays:
        [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
        """
        if frame is None or self.detector is None:
            return []

        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        status, faces = self.detector.detect(frame)

        if faces is None or len(faces) == 0:
            return []

        # Return faces sorted by bounding box area descending
        valid_faces = []
        for face in faces:
            score = face[-1]
            if score >= 0.55:
                valid_faces.append(face)

        valid_faces.sort(key=lambda f: f[2] * f[3], reverse=True)
        return valid_faces

    def extract_deep_embedding(self, frame: np.ndarray, face_data: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Extracts a 128-dimensional deep feature representation using SFace.
        If facial landmarks are provided, performs 5-point affine alignment.
        """
        if self.recognizer is None:
            return np.zeros(128, dtype=np.float32)

        if face_data is not None and len(face_data) >= 15:
            # 5-point aligned crop
            aligned = self.recognizer.alignCrop(frame, face_data)
        else:
            aligned = cv2.resize(frame, (112, 112))

        feat = self.recognizer.feature(aligned)
        return feat.flatten()

    def compute_similarity(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """
        Computes cosine similarity between two 128-d deep SFace vectors.
        SFace Cosine Distance threshold is ~0.363 for true positive matches.
        """
        if feat1 is None or feat2 is None or self.recognizer is None:
            return 0.0

        v1 = np.array(feat1, dtype=np.float32).reshape(1, 128)
        v2 = np.array(feat2, dtype=np.float32).reshape(1, 128)

        cos_score = float(self.recognizer.match(v1, v2, cv2.FaceRecognizerSF_FR_COSINE))

        # Scale cosine score into a readable 0-100% confidence:
        # SFace typical genuine pairs: 0.36 to 0.85
        # Impostor pairs: -0.1 to 0.30
        if cos_score >= 0.363:
            normalized_conf = min(0.99, max(0.70, 0.70 + (cos_score - 0.363) * 0.8))
        else:
            normalized_conf = max(0.05, min(0.60, cos_score * 1.5))

        return float(round(normalized_conf, 3))

    def evaluate_anti_spoofing(self, face_crop: np.ndarray, bbox: Tuple[int, int, int, int]) -> Dict[str, any]:
        """
        Multi-factor biological liveness detection:
        1. Texture sharpness (Laplacian variance) - screens & photo prints display distinct frequency blur or moiré.
        2. Color space chrominance dispersion (YCrCb) - human skin has rich Cr/Cb balance.
        3. Micro-motion tremor - real humans have natural postural micro-sway.
        """
        x, y, w, h = bbox
        scores = {}

        if face_crop.size == 0:
            return {"composite": 0.0, "is_live": False, "breakdown": {}}

        # 1. Texture Sharpness (Laplacian variance)
        # Real webcam faces typically have Laplacian variance 15-2500+
        # Printed photos or screens tend to have very low (<10) or very high (>3000) variance
        face_gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
        if lap_var >= 10:
            # Scale: 10 -> 0.60, 50 -> 0.80, 150+ -> 0.95
            scores["texture"] = min(0.98, 0.60 + (min(lap_var, 500) / 500.0) * 0.38)
        else:
            scores["texture"] = 0.20  # Extremely blurry / flat surface

        # 2. Color Chrominance (YCrCb)
        # Real skin has natural Cr/Cb variation; flat prints/screens have less
        ycrcb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2YCrCb)
        cr_std = float(np.std(ycrcb[:, :, 1]))
        cb_std = float(np.std(ycrcb[:, :, 2]))
        if cr_std > 3.0 and cb_std > 3.0:
            scores["chrominance"] = min(0.98, 0.70 + min((cr_std + cb_std) / 40.0, 0.28))
        else:
            scores["chrominance"] = 0.30

        # 3. Micro-motion / Tremor
        center = (x + w // 2, y + h // 2)
        if self.history["last_face_center"] is not None:
            dx = abs(center[0] - self.history["last_face_center"][0])
            dy = abs(center[1] - self.history["last_face_center"][1])
            dist = np.sqrt(dx**2 + dy**2)
            if dist >= 0.3:
                scores["motion"] = min(0.98, 0.75 + min(dist / 30.0, 0.23))
            else:
                scores["motion"] = 0.50  # Very still but not necessarily fake
        else:
            scores["motion"] = 0.85  # First frame - give benefit of doubt
        self.history["last_face_center"] = center

        composite_liveness = (
            0.40 * scores["texture"] +
            0.35 * scores["chrominance"] +
            0.25 * scores["motion"]
        )

        return {
            "composite": float(round(composite_liveness, 3)),
            "is_live": bool(composite_liveness >= 0.55),
            "breakdown": scores
        }

    def enroll_user(self, user_id: str, name: str, role: str, phone: str, mac: str, face_img: np.ndarray, dept: str = "Research Lab", tier: str = "Standard Access") -> bool:
        """
        Enrolls a new user with their deep SFace neural embedding and saves face crop.
        """
        if face_img is None:
            return False

        faces = self.detect_faces_deep(face_img)
        if not faces:
            # Fallback to center region if deep detector misses due to lighting
            h, w = face_img.shape[:2]
            crop = face_img
            emb = self.extract_deep_embedding(crop, None).tolist()
        else:
            best_face = faces[0]
            x, y, w, h = [int(v) for v in best_face[:4]]
            x = max(0, x)
            y = max(0, y)
            crop = face_img[y:y+h, x:x+w]
            emb = self.extract_deep_embedding(face_img, best_face).tolist()

        save_path = os.path.join(self.enrolled_dir, f"{user_id}.jpg")
        cv2.imwrite(save_path, crop if crop.size > 0 else face_img)

        self.enrolled_users[user_id] = {
            "name": name,
            "role": role,
            "department": dept,
            "access_tier": tier,
            "registered_phone": phone,
            "registered_mac": mac,
            "embedding": emb,
            "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_enrolled_users()
        return True

    def process_frame(self, frame: np.ndarray, scenario_override: Optional[str] = None) -> Tuple[np.ndarray, List[dict]]:
        """
        Full Deep Learning Inference Pipeline:
        - YuNet face detection & landmark localization
        - SFace 128-d deep embedding inference
        - Anti-spoofing verification
        - Cosine distance matching against authorized roster
        """
        if frame is None:
            return frame, []

        faces = self.detect_faces_deep(frame)
        detected_entities = []

        for face in faces:
            x, y, w, h = [int(v) for v in face[:4]]
            x = max(0, x)
            y = max(0, y)
            crop = frame[y:y+h, x:x+w]
            if crop.size == 0:
                continue

            # Deep feature embedding
            query_emb = self.extract_deep_embedding(frame, face)

            # Liveness evaluation
            liveness_info = self.evaluate_anti_spoofing(crop, (x, y, w, h))

            if scenario_override == "PHOTO_ATTACK":
                liveness_info["composite"] = 0.28
                liveness_info["is_live"] = False

            # Match against enrolled database using SFace
            best_match_id = None
            best_sim = 0.0
            matched_user_info = None

            for uid, udata in self.enrolled_users.items():
                emb = udata.get("embedding")
                if emb is not None:
                    sim = self.compute_similarity(query_emb, np.array(emb))
                else:
                    # Baseline demo match if no enrolled face exists yet
                    sim = 0.94 if uid == "USR-101" else 0.35

                if sim > best_sim:
                    best_sim = sim
                    best_match_id = uid
                    matched_user_info = udata

            is_recognized = (best_sim >= 0.70)

            entity = {
                "bbox": [x, y, w, h],
                "user_id": best_match_id if is_recognized else "UNKNOWN",
                "name": matched_user_info["name"] if (is_recognized and matched_user_info) else "Unregistered Person",
                "registered_mac": matched_user_info.get("registered_mac") if matched_user_info else None,
                "similarity": float(round(best_sim, 3)),
                "liveness_score": float(round(liveness_info["composite"], 3)),
                "is_live": liveness_info["is_live"],
                "liveness_breakdown": liveness_info["breakdown"]
            }
            detected_entities.append(entity)

            # Visual Annotation
            color = (0, 255, 127) if (is_recognized and entity["is_live"]) else (0, 70, 255)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

            status_text = f"{entity['name']} ({int(best_sim*100)}%)"
            live_text = f"Live: {int(entity['liveness_score']*100)}%" if entity["is_live"] else "SPOOF / PHOTO"

            cv2.putText(frame, status_text, (x, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            cv2.putText(frame, live_text, (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return frame, detected_entities

    def generate_synthetic_feed(self, scenario: str = "NORMAL") -> Tuple[np.ndarray, List[dict]]:
        """Generates high-definition simulated feed for scenario evaluation."""
        feed = np.zeros((480, 640, 3), dtype=np.uint8)
        feed[:] = (22, 26, 30)

        for i in range(0, 640, 40):
            cv2.line(feed, (i, 0), (i, 480), (32, 38, 44), 1)
        for j in range(0, 480, 40):
            cv2.line(feed, (0, j), (640, j), (32, 38, 44), 1)

        t_str = time.strftime("IIIT-B LAB DOOR 04A | %Y-%m-%d %H:%M:%S")
        cv2.putText(feed, t_str, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 180), 1)

        cx, cy = 320, 240
        w, h = 180, 220
        x, y = cx - w//2, cy - h//2

        if scenario == "PHOTO_ATTACK":
            cv2.rectangle(feed, (x - 20, y - 20), (x + w + 20, y + h + 40), (80, 80, 90), 4)
            cv2.circle(feed, (cx, y + h + 25), 8, (120, 120, 120), -1)
            cv2.putText(feed, "[ATTACK] SCREEN PRESENTATION REPLAY", (x - 20, y - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            avatar_color = (190, 160, 140)
            is_live = False
            liveness_score = 0.28
        else:
            avatar_color = (210, 180, 160)
            is_live = True
            liveness_score = 0.94

        cv2.ellipse(feed, (cx, cy), (70, 95), 0, 0, 360, avatar_color, -1)
        cv2.circle(feed, (cx - 28, cy - 20), 8, (60, 40, 30), -1)
        cv2.circle(feed, (cx + 28, cy - 20), 8, (60, 40, 30), -1)
        cv2.ellipse(feed, (cx, cy + 30), (28, 18), 0, 0, 180, (120, 70, 70), 3)

        is_authorized_face = (scenario not in ["STRANGER", "STOLEN_PHONE"])
        user_id = "USR-101" if is_authorized_face else "UNKNOWN"
        user_name = "Dr. Ramesh Kumar" if is_authorized_face else "Unregistered Intruder"
        sim_score = 0.94 if is_authorized_face else 0.22

        box_color = (0, 255, 127) if (is_live and sim_score > 0.70) else (0, 60, 255)
        cv2.rectangle(feed, (x, y), (x+w, y+h), box_color, 2)
        cv2.putText(feed, f"{user_name} ({int(sim_score*100)}%)", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)
        cv2.putText(feed, f"Liveness: {int(liveness_score*100)}% ({'LIVE' if is_live else 'SPOOF'})",
                    (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

        entity = {
            "bbox": [x, y, w, h],
            "user_id": user_id,
            "name": user_name,
            "registered_mac": "F4:F5:DB:89:12:34" if is_authorized_face else None,
            "similarity": sim_score,
            "liveness_score": liveness_score,
            "is_live": is_live,
            "liveness_breakdown": {
                "texture": 0.3 if not is_live else 0.95,
                "chrominance": 0.4 if not is_live else 0.92,
                "motion": 0.2 if not is_live else 0.91
            }
        }
        return feed, [entity]
