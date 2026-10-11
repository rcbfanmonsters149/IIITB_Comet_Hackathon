import time
import threading
from typing import Dict, Optional

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

class MCUDriver:
    """
    MCU Module: Interfaces with ESP32 / Arduino / USB Relay microcontroller
    to actuate physical door locks, RGB indicator LEDs, and piezo buzzers.
    Features automated failover to virtual hardware emulation when physical board is detached.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_connected = False

        # Physical hardware state representation
        self.state = {
            "relay_state": "LOCKED",        # "LOCKED" | "UNLOCKED"
            "solenoid_voltage_v": 0.0,      # 0.0V (Resting) | 12.0V (Energized)
            "rgb_led": "BLUE_IDLE",         # "BLUE_IDLE", "GREEN_GRANTED", "RED_DENIED"
            "buzzer": "OFF",                # "OFF", "CHIME", "ALARM"
            "last_action_timestamp": time.time(),
            "door_open_duration_sec": 3.0,
            "hardware_mode": "VIRTUAL_EMULATOR"
        }

        self.lock_timer = None
        self._init_connection()

    def _init_connection(self):
        """Attempts to discover and connect to a serial MCU on COM ports."""
        if not SERIAL_AVAILABLE:
            print("[MCU] pyserial unavailable. Operating in Virtual MCU mode.")
            return

        try:
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            target_port = self.port or (available_ports[0] if available_ports else None)

            if target_port:
                print(f"[MCU] Attempting connection to hardware on {target_port}...")
                self.serial_conn = serial.Serial(target_port, self.baudrate, timeout=1.0)
                self.is_connected = True
                self.state["hardware_mode"] = f"PHYSICAL_HARDWARE ({target_port})"
                print(f"[MCU] Successfully connected to physical MCU on {target_port}!")
            else:
                print("[MCU] No serial COM ports detected. Running high-precision Virtual MCU Emulation.")
        except Exception as e:
            print(f"[MCU] Serial connection warning: {e}. Defaulting to Virtual MCU Emulation.")
            self.is_connected = False

    def trigger_unlock(self, duration_sec: float = 3.0) -> Dict[str, any]:
        """
        Actuates door unlock sequence:
        1. Energizes relay (12V solenoid strike pulls back).
        2. Sets Green LED.
        3. Plays single chime.
        4. Automatically re-locks after duration_sec.
        """
        self.state["relay_state"] = "UNLOCKED"
        self.state["solenoid_voltage_v"] = 12.0
        self.state["rgb_led"] = "GREEN_GRANTED"
        self.state["buzzer"] = "CHIME"
        self.state["last_action_timestamp"] = time.time()

        # Send command over serial if physical hardware attached
        if self.is_connected and self.serial_conn:
            try:
                self.serial_conn.write(b"UNLOCK\n")
            except Exception as e:
                print(f"[MCU] Serial write failed: {e}")

        # Cancel previous pending relock timers
        if self.lock_timer and self.lock_timer.is_alive():
            self.lock_timer.cancel()

        # Schedule automatic relock
        self.lock_timer = threading.Timer(duration_sec, self._auto_relock)
        self.lock_timer.start()

        return dict(self.state)

    def trigger_alarm(self, duration_sec: float = 2.5) -> Dict[str, any]:
        """
        Actuates alarm / security warning sequence:
        1. Keeps door LOCKED.
        2. Flashes Red LED.
        3. Emits loud pulsing buzzer alarm.
        """
        self.state["relay_state"] = "LOCKED"
        self.state["solenoid_voltage_v"] = 0.0
        self.state["rgb_led"] = "RED_DENIED"
        self.state["buzzer"] = "ALARM"
        self.state["last_action_timestamp"] = time.time()

        if self.is_connected and self.serial_conn:
            try:
                self.serial_conn.write(b"ALARM\n")
            except Exception as e:
                print(f"[MCU] Serial write failed: {e}")

        # Reset to idle after duration
        threading.Timer(duration_sec, self._reset_to_idle).start()
        return dict(self.state)

    def _auto_relock(self):
        """Relocks solenoid after access window passes."""
        self.state["relay_state"] = "LOCKED"
        self.state["solenoid_voltage_v"] = 0.0
        self.state["rgb_led"] = "BLUE_IDLE"
        self.state["buzzer"] = "OFF"
        self.state["last_action_timestamp"] = time.time()

        if self.is_connected and self.serial_conn:
            try:
                self.serial_conn.write(b"LOCK\n")
            except Exception:
                pass

    def _reset_to_idle(self):
        """Resets indicators to idle state."""
        self.state["rgb_led"] = "BLUE_IDLE"
        self.state["buzzer"] = "OFF"

    def get_status(self) -> Dict[str, any]:
        """Returns live MCU telemetry."""
        return dict(self.state)
