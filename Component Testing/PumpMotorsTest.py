# Simple code for running DC motors- such as the pump

import RPi.GPIO as GPIO
from time import sleep

# Pin Definitions
in1, in2, en = 27, 22, 17
GPIO.setmode(GPIO.BCM)
GPIO.setup([in1, in2, en], GPIO.OUT)
GPIO.output([in1, in2], GPIO.LOW)
p = GPIO.PWM(en, 1000)
p.start(25)

print("\nThe default speed & direction of motor is LOW & Forward.....")
print("Commands: r-run s-stop f-forward b-backward l-low m-medium h-high e->")

temp1 = 1  # Default direction: forward
speeds = {'l': 25, 'm': 50, 'h': 80}

while True:
    x = input().strip().lower()

    if x in {'r', 'f', 'b'}:
        temp1 = 1 if x in {'r', 'f'} else 0
        GPIO.output(in1, GPIO.HIGH if temp1 else GPIO.LOW)
        GPIO.output(in2, GPIO.LOW if temp1 else GPIO.HIGH)
        print("Running forward" if temp1 else "Running backward")

    elif x == 's':
        GPIO.output([in1, in2], GPIO.LOW)
        print("Stopped")

    elif x in speeds:
        p.ChangeDutyCycle(speeds[x])
        print(f"Speed set to {x.upper()}")

    elif x == 'e':
        GPIO.cleanup()
        break

    else:
        print("Invalid command! Use r, s, f, b, l, m, h, or e.")
