# Move servo_test.py to archive/
import os
import shutil

src = os.path.join(os.path.dirname(__file__), 'servo_test.py')
dst = os.path.join(os.path.dirname(__file__), 'archive', 'servo_test.py')
if os.path.exists(src):
    shutil.move(src, dst)

import time
import pigpio

SERVO_PIN = 18  # Chamber lid servo GPIO
PULSE_WIDTHS = [500, 1000, 1500, 2000, 2500, 3000, 4000, 4500]
HOLD_TIME = 3  # seconds to hold each position

pi = pigpio.pi()
if not pi.connected:
    print("[ERROR] Cannot connect to pigpio daemon. Start it with: sudo pigpiod")
    exit(1)

try:
    print(f"Sweeping servo on GPIO {SERVO_PIN} through pulse widths: {PULSE_WIDTHS} µs")
    while True:
        for pw in PULSE_WIDTHS:
            print(f"Setting pulse width: {pw} µs")
            pi.set_servo_pulsewidth(SERVO_PIN, pw)
            time.sleep(HOLD_TIME)
except KeyboardInterrupt:
    pass
finally:
    pi.set_servo_pulsewidth(SERVO_PIN, 0)
    pi.stop()
    print("[INFO] Servo signal off. GPIO cleaned up.")
