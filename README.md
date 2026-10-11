# IIIT-B Contactless Access Control: Face + Proximity Fusion

[![Smart Campus](https://img.shields.io/badge/Domain-Smart_Campus_/_Industrial-blue.svg)](#)
[![Tags](https://img.shields.io/badge/Tags-CAM_|_WIFI_|_AUDIO_|_MCU-orange.svg)](#)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-green.svg)](#)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-teal.svg)](#)

A zero-friction, high-security **Two-Factor Authentication (2FA) Multi-Modal Access Control System** for campus research laboratories, server rooms, and industrial cleanrooms.

---

## 1. System Architecture & The 4-Tag Mapping

Traditional face recognition systems are vulnerable to **presentation attacks** (photo prints, tablet screen replays) and **accidental triggers** (authorized personnel walking past the door). This system fuses four sensory and edge actuation layers:

```
              ┌─────────────────────────────────────────────────────────┐
              │             MULTI-MODAL SENSOR INGESTION                │
              └─────────────────────────────────────────────────────────┘
                     │                     │                     │
                     ▼                     ▼                     ▼
          ┌─────────────────────┐┌───────────────────┐┌───────────────────┐
          │      📷 CAM         ││     📶 WIFI       ││     🎤 AUDIO      │
          │  OpenCV + Liveness  ││ RSSI Proximity    ││ Ultrasonic Token │
          │  (Face Embeddings)  ││ (Paired MAC)      ││ (19 kHz Near-Fld)│
          └──────────┬──────────┘└─────────┬─────────┘└─────────┬─────────┘
                     │                     │                    │
                     └─────────────────────┼────────────────────┘
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │         SPATIAL-TEMPORAL AI FUSION GATEWAY              │
              │  Confidence = 0.45(Face) + 0.30(WiFi) + 0.25(Audio)     │
              └────────────────────────────┬────────────────────────────┘
                                           │
                         ┌─────────────────┴─────────────────┐
                         ▼                                   ▼
              ┌──────────────────────┐            ┌─────────────────────┐
              │    ACCESS GRANTED    │            │    ACCESS DENIED    │
              │   ⚡ MCU (ESP32)     │            │  Audible Alarm /    │
              │   • Energize Relay   │            │  Forensic Snapshot  │
              │   • 12V Solenoid Open│            │  Log Generated      │
              │   • Green LED Chime  │            │                     │
              └──────────────────────┘            └─────────────────────┘
```

### Sensor Modules:
1. **`CAM` (Computer Vision)**:
   - Detects faces and computes normalized feature embeddings.
   - Evaluates **biological liveness & anti-spoofing**:
     - High-frequency texture analysis (Laplacian variance) to differentiate physical skin from screen pixels or paper prints.
     - Chrominance dispersion ($YCrCb$) reflectance checks.
     - Micro-motion tremor tracking.
2. **`WIFI` (Radio Proximity)**:
   - Monitors device signal strength ($RSSI$).
   - Enforces a near-field threshold ($RSSI \ge -48\text{ dBm} \implies \le 1.0\text{m}$).
   - Correlates the detected MAC address with the facial identity in the enrolled database.
3. **`AUDIO` (Acoustic Validation)**:
   - Near-field ultrasonic token verification ($18.5\text{ kHz} - 19.5\text{ kHz}$ chirp from user's phone). High-frequency sound rapidly attenuates with distance, confirming physical presence at the terminal.
   - Spoken challenge-response option for high-tier authentication.
4. **`MCU` (Microcontroller & Lock Actuation)**:
   - ESP32 / Arduino / USB relay driver over Serial (`115200 baud`).
   - Actuates 5V relay module (driving 12V electromagnetic door strike), RGB status LED, and piezo buzzer.
   - Features automated fallback to **Virtual Hardware Emulation** when running without physical development boards connected.

---

## 2. Decision Truth Matrix

| Face Match ($S_{face} \ge 0.75$) | Biological Liveness ($S_{live} \ge 0.70$) | Wi-Fi Proximity ($RSSI \ge -48\text{dBm}$) | Ultrasonic Audio ($S_{audio} \ge 0.70$) | System Decision | Physical Action |
| :---: | :---: | :---: | :---: | :---: | :--- |
| ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | **ACCESS_GRANTED** | MCU fires 3s relay pulse, Green LED, chime. |
| ✅ Yes | ❌ **No (Spoof)** | ✅ Yes | ✅ Yes | **DENIED_PRESENTATION_ATTACK** | Red warning LED, warning buzzer alarm. |
| ✅ Yes | ✅ Yes | ❌ **No (Far/Absent)**| ❌ No | **DENIED_DEVICE_ABSENT** | Lock holds secure (Accidental corridor walk-by). |
| ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | **DENIED_STOLEN_DEVICE** | Lock holds secure, security flag logged. |

---

## 3. Quick Start & Execution

### 1. Launch the Server
From the project directory:
```powershell
python main.py
```

### 2. Open the SOC Dashboard
Navigate to:
```
http://localhost:8000
```

### 3. Interactive Scenario Testing
The dashboard includes an interactive evaluation suite to verify each scenario:
- **Scenario 1: Authorized Walk-up** $\to$ Dr. Ramesh Kumar with phone at door $\to$ Unlocks relay!
- **Scenario 2: Presentation Attack** $\to$ Screen/Photo spoof $\to$ Triggers alarm buzzer!
- **Scenario 3: Accidental Walk-by** $\to$ Subject walking in hallway at 3.5m $\to$ Lock remains secure!
- **Scenario 4: Stolen Phone** $\to$ Registered phone at door, unknown face $\to$ Lock remains secure!

---

## 4. Hardware Pinout (ESP32 DevKit)

| Peripheral | ESP32 Pin | Logic |
| :--- | :--- | :--- |
| **5V Relay Module (Solenoid Strike)** | `GPIO 26` | HIGH = Energized (Unlocked) |
| **RGB LED (Red)** | `GPIO 17` | PWM |
| **RGB LED (Green)** | `GPIO 18` | PWM |
| **RGB LED (Blue)** | `GPIO 19` | PWM |
| **Active Piezo Buzzer** | `GPIO 23` | Tone Output |
| **Serial Communication** | `USB / COM Port` | 115200 Baud |

Firmware source: `firmware/esp32_access_controller.ino`.
