import time
import pigpio

SERVO_PIN = 18  # Chamber lid servo GPIO
PULSE_WIDTH = 1500  # Try 500, 1000, 1500, 2000, 2500, 3000, 4000, 4500

pi = pigpio.pi()
if not pi.connected:
    print("[ERROR] Cannot connect to pigpio daemon. Start it with: sudo pigpiod")
    exit(1)

try:
    print(f"Setting servo on GPIO {SERVO_PIN} to {PULSE_WIDTH} µs. Press Ctrl+C to stop.")
    pi.set_servo_pulsewidth(SERVO_PIN, PULSE_WIDTH)
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    pi.set_servo_pulsewidth(SERVO_PIN, 0)
    pi.stop()
    print("[INFO] Servo signal off. GPIO cleaned up.")
