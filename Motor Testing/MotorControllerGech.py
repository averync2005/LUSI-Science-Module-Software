# This shit didn't work
# The motors were getting quick pulse sequences causing them
# to move back a forth sparatically. 

import time
import curses
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
    

def motor_control(stdscr):
    curses.curs_set(0)  # Hide cursor
    curses.halfdelay(1)  # Small delay to avoid flickering (1 = 0.1s)
    
    intensity = 3
    motor_speeds = {"motor1": 15, "motor2": 15}  # Store motor states
    key_states = {}  # Track which keys are being held
    action_message = "Idle"

    while True:
        stdscr.clear()  # Clear screen before printing new text
        stdscr.addstr("Controls:\nW - Motor 1 Up\nS - Motor 1 Down\nE - Motor 2 Up\nD - Motor 2 Down\nP - Pour Soil\nO - Raise Collector\nQ - Quit\n")
        stdscr.addstr(f"\nCurrent Action: {action_message}")  # Display the latest action
        stdscr.refresh()

        key = stdscr.getch()

        if key != -1:  # Valid key press
            key_states[key] = True

        # Process active keys
        if ord('w') in key_states:
            action_message = "Motor 1: Moving Up"
            motor_speeds["motor1"] = 15 + intensity / 20
        elif ord('s') in key_states:
            action_message = "Motor 1: Moving Down"
            motor_speeds["motor1"] = 15 - intensity / 20
        else:
            motor_speeds["motor1"] = 15  # Stop motor when key is released

        if ord('e') in key_states:
            action_message = "Motor 2: Moving Up"
            motor_speeds["motor2"] = 15 + intensity / 20
        elif ord('d') in key_states:
            action_message = "Motor 2: Moving Down"
            motor_speeds["motor2"] = 15 - intensity / 20
        else:
            motor_speeds["motor2"] = 15  # Stop motor when key is released

        if ord('p') in key_states:
            action_message = "Pouring Soil"
            setAngle(120)
        elif ord('o') in key_states:
            action_message = "Raising Collector"

        if ord('q') in key_states:
            break

        # Apply both motor speeds simultaneously
        set_motor_speed(motor1_pwm, motor_speeds["motor1"])
        set_motor_speed(motor2_pwm, motor_speeds["motor2"])

        # Remove key from state (acts as key release)
        key_states.clear()

    motor1_pwm.stop()
    motor2_pwm.stop()
    SERVO_pwm.stop()
    GPIO.cleanup()

curses.wrapper(motor_control)
