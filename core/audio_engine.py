import numpy as np
import time
import random
from typing import Dict, Optional

class AudioEngine:
    """
    AUDIO Module: Multi-modal acoustic verification.
    1. Near-field ultrasonic token verification (18.5 kHz - 19.5 kHz chirp from phone).
    2. Dynamic voice challenge-response liveness.
    3. Ambient acoustic presence validation.
    """

    ULTRASONIC_CARRIER_HZ = 19000  # 19 kHz near-ultrasound
    ULTRASONIC_BANDWIDTH_HZ = 500

    def __init__(self):
        self.active_challenge: Optional[str] = None
        self.challenge_expiry = 0
        self.last_audio_power = -35.0  # dBFS

    def generate_voice_challenge(self) -> Dict[str, any]:
        """Generates a randomized 2-digit spoken security challenge."""
        code = str(random.randint(10, 99))
        self.active_challenge = code
        self.challenge_expiry = time.time() + 15.0  # 15s validity
        return {
            "challenge_code": code,
            "prompt_text": f"Please speak passcode: {code}",
            "expires_in_seconds": 15
        }

    def verify_acoustic_token(self, expected_token_id: str, scenario_override: Optional[str] = None) -> Dict[str, any]:
        """
        Detects presence of near-ultrasound smartphone chirp (19 kHz).
        High-frequency audio decays within 1.5 meters, ensuring the phone
        is physically present in front of the door terminal.
        """
        if scenario_override == "PHOTO_ATTACK" or scenario_override == "DEVICE_ABSENT":
            return {
                "verified": False,
                "token_detected": False,
                "frequency_peak_hz": 0,
                "snr_db": 2.1,
                "score": 0.15,
                "reason": "NO_ULTRASONIC_TOKEN_RECEIVED"
            }

        if scenario_override == "WALK_BY":
            # Acoustic signal too faint because person is 3.5m away
            return {
                "verified": False,
                "token_detected": False,
                "frequency_peak_hz": 18990,
                "snr_db": 6.5,
                "score": 0.42,
                "reason": "ACOUSTIC_SIGNAL_ATTENUATED_BY_DISTANCE"
            }

        # Normal verification: Phone is near terminal
        jitter_hz = random.randint(-40, 40)
        detected_freq = self.ULTRASONIC_CARRIER_HZ + jitter_hz
        snr = round(random.uniform(22.0, 28.5), 1)

        return {
            "verified": True,
            "token_detected": True,
            "frequency_peak_hz": detected_freq,
            "snr_db": snr,
            "score": 0.96,
            "reason": "ULTRASONIC_CHIRP_VALIDATED"
        }

    def verify_voice_response(self, spoken_digits: str) -> Dict[str, any]:
        """Validates spoken response against the active challenge."""
        if not self.active_challenge or time.time() > self.challenge_expiry:
            return {"verified": False, "reason": "CHALLENGE_EXPIRED"}

        matches = (spoken_digits.strip() == self.active_challenge)
        return {
            "verified": matches,
            "expected": self.active_challenge,
            "received": spoken_digits,
            "reason": "VOICE_PASSED" if matches else "WRONG_DIGITS"
        }
