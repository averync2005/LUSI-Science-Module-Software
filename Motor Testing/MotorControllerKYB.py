# LUSI code that was used to test the rover right before URC deadline

import time
import RPi.GPIO as GPIO

# Pin Configuration
MOTOR1_PIN = 5
MOTOR2_PIN = 6
SERVO_PIN = 27
PWM_FREQ = 100  # (should be within 50Hz to 200Hz)

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR1_PIN, GPIO.OUT)
GPIO.setup(MOTOR2_PIN, GPIO.OUT)
GPIO.setup(SERVO_PIN, GPIO.OUT)

# Initialize PWM for both motors
motor1_pwm = GPIO.PWM(MOTOR1_PIN, PWM_FREQ)
motor2_pwm = GPIO.PWM(MOTOR2_PIN, PWM_FREQ)
SERVO_pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz PWM frequency for SERVO

# Start PWM with 0% duty cycle (motors off)
motor1_pwm.start(0)
motor2_pwm.start(0)
SERVO_pwm.start(0)

def set_motor_speed(motor_pwm, pulse_width_us):
    motor_pwm.ChangeDutyCycle(pulse_width_us)

def setAngle(angle):
    duty = angle / 18 + 2  # Convert angle to duty cycle
    SERVO_pwm.ChangeDutyCycle(duty)
    time.sleep(0.3)  # Allow servo to reach position
    SERVO_pwm.ChangeDutyCycle(0)  # Stop sending signal to prevent jitter

intensity = 1000
selectedMotor = motor1_pwm



print("""
Controls:
- Type 'w'  → Move Up (Full Reverse) at 1000 µs
- Type 's'  → Move Down (Full Forward) at 2000 µs
- Type '1'  → Select Motor 1
- Type '2'  → Select Motor 2
- Type 'p'  → Pour soil collected
- Type 'o'  → Raise soil collector
- Type 'q'  → Quit
""")

intensity = 3
duration = 1
try:
    while True:
        command = input("Enter command: ").strip().lower()
        if command == "b":
            set_motor_speed(motor1_pwm, 13.5)
            set_motor_speed(motor2_pwm, 14.5)
        if command == "t":
            set_motor_speed(motor1_pwm, 15)  # Stops motor
            set_motor_speed(motor2_pwm, 14.5)
        if command == "1":
            #set_motor_speed(selectedMotor, 15)  # Stops motor
            selectedMotor = motor1_pwm
            print("Selected Motor 1")
            continue
        elif command == "2":
            #set_motor_speed(selectedMotor, 15)  # Stops motor
            selectedMotor = motor2_pwm
            print("Selected Motor 2")
            continue
        elif command == "q":
            print("Quitting...")
            break

        elif command == "p":
            print("Collecting")
            setAngle(120)
            continue
        elif command == "o":
            print("Pouring")


        intensity = int(input("Enter intensity (1-100): "))
        duration = int(input("Enter Time: "))

        if command == "w":
            print("Moving up (1000 µs)")
            set_motor_speed(selectedMotor, 15 + intensity/20)
        elif command == "s":
            print("Full Forward (2000 µs)")
            set_motor_speed(selectedMotor, 15 - intensity/20)

        else:
            print("Invalid command. Please try again.")

        time.sleep(duration)
        set_motor_speed(motor1_pwm, 15)
        set_motor_speed(motor2_pwm, 15)

except KeyboardInterrupt:
    print("Stopping motors")
finally:
    motor1_pwm.stop()
    motor2_pwm.stop()
    SERVO_pwm.stop()
    GPIO.cleanup()  # Reset GPIO
