/*
  =============================================================================
  IIIT-B Smart Campus Contactless Access Controller (MCU Firmware)
  Target Hardware: ESP32 DevKit V1 / Arduino Uno / Nano / Raspberry Pi Pico
  Peripherals:
    - 5V Relay Module (Controls 12V Solenoid Door Strike) on GPIO 26
    - RGB LED Indicator (Common Cathode) on GPIO 17, 18, 19
    - Active Piezo Buzzer on GPIO 23
    - Serial Baud: 115200 bps
  =============================================================================
*/

#define RELAY_PIN     26
#define LED_RED_PIN   17
#define LED_GREEN_PIN 18
#define LED_BLUE_PIN  19
#define BUZZER_PIN    23

unsigned long unlockTimestamp = 0;
bool isUnlocked = false;
const unsigned long UNLOCK_WINDOW_MS = 3000;

void setRGB(int r, int g, int b) {
  analogWrite(LED_RED_PIN, r);
  analogWrite(LED_GREEN_PIN, g);
  analogWrite(LED_BLUE_PIN, b);
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_BLUE_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Initial State: Locked (Relay LOW / Active LOW depends on relay board)
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  setRGB(0, 50, 255); // Blue Idle

  Serial.println("[MCU_READY] IIIT-B Access Controller Online");
}

void loop() {
  // Check for Serial Commands from Host PC Vision/Fusion Engine
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "UNLOCK") {
      isUnlocked = true;
      unlockTimestamp = millis();
      digitalWrite(RELAY_PIN, HIGH);     // Energize relay
      setRGB(0, 255, 50);                 // Bright Green
      tone(BUZZER_PIN, 2000, 150);        // Success Beep
      Serial.println("[ACK] RELAY_ENERGIZED_UNLOCKED");
    }
    else if (cmd == "ALARM") {
      digitalWrite(RELAY_PIN, LOW);
      setRGB(255, 0, 0);                 // Red Warning
      // 3 rapid warning pulses
      for (int i = 0; i < 3; i++) {
        tone(BUZZER_PIN, 800, 100);
        delay(120);
      }
      setRGB(0, 50, 255);                // Return to Blue Idle
      Serial.println("[ACK] ALARM_TRIGGERED");
    }
    else if (cmd == "LOCK") {
      isUnlocked = false;
      digitalWrite(RELAY_PIN, LOW);
      setRGB(0, 50, 255);                // Blue Idle
      Serial.println("[ACK] RELAY_LOCKED");
    }
    else if (cmd == "STATUS") {
      Serial.print("[STATUS] Relay: ");
      Serial.print(isUnlocked ? "UNLOCKED" : "LOCKED");
      Serial.print(" | Uptime: ");
      Serial.println(millis());
    }
  }

  // Automatic Door Relock Timer
  if (isUnlocked && (millis() - unlockTimestamp >= UNLOCK_WINDOW_MS)) {
    isUnlocked = false;
    digitalWrite(RELAY_PIN, LOW);        // De-energize solenoid lock
    setRGB(0, 50, 255);                  // Back to Blue Idle
    Serial.println("[EVENT] AUTO_RELOCK_ENGAGED");
  }
}
