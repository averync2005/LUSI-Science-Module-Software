#####################################################################################################################
# LUSI Science Module - Motor Controller CLI
#
# This script provides a terminal-based command-line interface for controlling the 4 motors on the LUSI Science Module.
# It runs on a Raspberry Pi and communicates over Ethernet to the base station computer.
#
# Motors:
#   1. Auger Motor
#     - NEO 550 (via REV Spark MAX)
#     - Digs soil
#     - Gearbox: 3× 4:1 UltraPlanetary = 64:1 total reduction
#     - Direction: forward only
#   2. Platform Motor
#     - NEO 550 (via REV Spark MAX)
#     - Raises/lowers the soil collection platform
#     - Gearbox: 2× 3:1 + 1× 4:1 UltraPlanetary = 36:1 total reduction
#     - Direction: forward (up) AND reverse (down)
#   3. Testing Chamber Lid
#     - SM-S2309S servo
#     - rotates the lid of the testing chamber
#                          Range: 0–180°, ±1° fine control
#   4. Soil Dropper     - SG92R micro servo - rotates a lid that drops collected soil
#                          Range: 0–180°, ±1° fine control
#####################################################################################################################




#####################################################################################################################
# Importing Program Libraries
#   - time:
#       - Adds small delays so the program doesn't hog the CPU
#       - Gives servos time to physically reach their target angle
#   - curses:
#       - Handles live key presses without needing to press "Enter"
#       - Redraws the terminal display in real time
#       - Enables an interactive CLI (command-line interface)
#   - RPi.GPIO:
#       - Controls the Raspberry Pi's GPIO (General Purpose Input/Output) pins
#       - Configures pins as outputs so we can send PWM signals
#       - PWM (Pulse Width Modulation) signals tell the Spark MAX and servos what to do
#####################################################################################################################

import time
import curses
import RPi.GPIO as GPIO




#####################################################################################################################
# GPIO Pin Assignments (BCM numbering)
#   - Each motor is connected to one GPIO pin on the Raspberry Pi
#   - BCM = Broadcom pin numbering (the numbers printed on Pi pinout diagrams)
#   - Change these if you wire motors to different pins
#####################################################################################################################

AUGER_PIN       = 12  # NEO 550 → Spark MAX controller → GPIO 12
PLATFORM_PIN    = 13  # NEO 550 → Spark MAX controller → GPIO 13
CHAMBER_LID_PIN = 18  # SM-S2309S servo → GPIO 18
SOIL_DROP_PIN   = 19  # SG92R micro servo → GPIO 19




#####################################################################################################################
# PWM Configuration
#   - All four motors use 50 Hz PWM (one pulse every 20 ms)
#   - 50 Hz is the standard for both hobby servos and the REV Spark MAX
#
# How the Spark MAX interprets the PWM signal (NEO 550 motors):
#   - The Spark MAX reads the width of each pulse (in microseconds):
#       1000 µs  →  full reverse
#       1500 µs  →  neutral / stop
#       2000 µs  →  full forward
#   - At 50 Hz the period is 20 000 µs, so duty-cycle percentages are:
#       5.0 %  →  1000 µs  →  full reverse
#       7.5 %  →  1500 µs  →  neutral
#      10.0 %  →  2000 µs  →  full forward
#
# How standard servos interpret the PWM signal:
#   - Pulse width maps to shaft angle:
#       ~500 µs (2.5 %)  →    0°
#      ~1500 µs (7.5 %)  →   90°
#      ~2500 µs (12.5 %) →  180°
#   - The formula used here:  duty% = (angle / 18) + 2.5
#####################################################################################################################

PWM_FREQUENCY = 50  # 50 Hz for Spark MAX and hobby servos

# Spark MAX duty-cycle boundaries (percent)
SPARK_NEUTRAL = 7.5  # 1500 µs - motor stopped
SPARK_MAX_FWD = 10.0  # 2000 µs - full speed forward
SPARK_MAX_REV = 5.0  # 1000 µs - full speed reverse

# Speed/angle adjustment step sizes
SPEED_STEP = 5  # Each key press changes speed by ±5 %
ANGLE_STEP = 1  # Each key press changes angle by ±1°




#####################################################################################################################
# Motor State Variables
#   - These keep track of whether each motor is active and its current speed/angle
#   - "selected_motor" tracks which motor the user is currently controlling (1–4)
#   - NEO 550 motors store speed as a percentage (0–100 %)
#   - Servos store angle in degrees (0–180°)
#   - Platform motor also stores its current direction ("up" or "down")
#####################################################################################################################

selected_motor = None  # Which motor is currently selected (1, 2, 3, or 4)

# Motor 1 - Auger (forward only)
auger_active = False
auger_speed  = 0  # 0–100 %

# Motor 2 - Platform (bidirectional)
platform_active    = False
platform_speed     = 0  # 0–100 %
platform_direction = "up"  # "up" (forward) or "down" (reverse)

# Motor 3 - Chamber lid servo
chamber_lid_active = False
chamber_lid_angle  = 0  # 0–180°

# Motor 4 - Soil dropper servo
soil_drop_active = False
soil_drop_angle  = 0  # 0–180°




#####################################################################################################################
# GPIO Setup
#   - Tell the Pi we are using BCM pin numbering
#   - Configure each motor pin as an output (we send signals OUT to the motors)
#####################################################################################################################

GPIO.setmode(GPIO.BCM)
GPIO.setup(AUGER_PIN,       GPIO.OUT)
GPIO.setup(PLATFORM_PIN,    GPIO.OUT)
GPIO.setup(CHAMBER_LID_PIN, GPIO.OUT)
GPIO.setup(SOIL_DROP_PIN,   GPIO.OUT)




#####################################################################################################################
# Initializing PWM Objects
#   - Create a PWM object for each motor pin at 50 Hz
#   - Start each PWM output at the appropriate "off" duty cycle:
#       • Spark MAX motors start at 7.5 % (neutral / stopped)
#       • Servos start at 0 % (signal off - holds last position or relaxes)
#####################################################################################################################

pwm_auger       = GPIO.PWM(AUGER_PIN,       PWM_FREQUENCY)
pwm_platform    = GPIO.PWM(PLATFORM_PIN,    PWM_FREQUENCY)
pwm_chamber_lid = GPIO.PWM(CHAMBER_LID_PIN, PWM_FREQUENCY)
pwm_soil_drop   = GPIO.PWM(SOIL_DROP_PIN,   PWM_FREQUENCY)

pwm_auger.start(SPARK_NEUTRAL)  # NEO 550 - start at neutral
pwm_platform.start(SPARK_NEUTRAL)  # NEO 550 - start at neutral
pwm_chamber_lid.start(0)  # Servo - signal off
pwm_soil_drop.start(0)  # Servo - signal off




#####################################################################################################################
# Helper Function - Convert Speed % to Spark MAX Duty Cycle
#
#   Parameters:
#       speed_pct  - motor speed as a percentage, 0 to 100
#       direction  - "forward" or "reverse"
#
#   Returns:
#       The PWM duty-cycle percentage to send to the Spark MAX
#
#   How it works:
#       Forward:  duty = 7.5 + (speed / 100) × 2.5   →  7.5 % (stop) to 10.0 % (full forward)
#       Reverse:  duty = 7.5 − (speed / 100) × 2.5   →  7.5 % (stop) to  5.0 % (full reverse)
#####################################################################################################################

def speed_to_spark_duty(speed_pct, direction="forward"):
    if direction == "forward":
        return SPARK_NEUTRAL + (speed_pct / 100.0) * (SPARK_MAX_FWD - SPARK_NEUTRAL)
    else:
        return SPARK_NEUTRAL - (speed_pct / 100.0) * (SPARK_NEUTRAL - SPARK_MAX_REV)




#####################################################################################################################
# Helper Function - Convert Angle to Servo Duty Cycle
#
#   Parameters:
#       angle  - desired servo angle in degrees, 0 to 180
#
#   Returns:
#       The PWM duty-cycle percentage to send to the servo
#
#   How it works:
#       duty = (angle / 18) + 2.5
#       This maps 0° → 2.5 %, 90° → 7.5 %, 180° → 12.5 %
#####################################################################################################################

def angle_to_servo_duty(angle):
    # Clamp the angle to the valid range
    angle = max(0, min(180, angle))
    return (angle / 18.0) + 2.5




#####################################################################################################################
# Motor Control Functions
#   - set_spark_motor():  sends the correct duty cycle to a Spark MAX (NEO 550)
#   - set_servo_angle():  sends the correct duty cycle to a hobby servo
#   - stop_all_motors():  immediately stops every motor and resets all state
#####################################################################################################################

def set_spark_motor(pwm_obj, speed_pct, direction="forward"):
    """Send a speed command to a NEO 550 motor via its Spark MAX controller."""
    duty = speed_to_spark_duty(speed_pct, direction)
    pwm_obj.ChangeDutyCycle(duty)


def set_servo_angle(pwm_obj, angle):
    """Move a servo motor to the specified angle (0–180°)."""
    angle = max(0, min(180, angle))
    duty = angle_to_servo_duty(angle)
    pwm_obj.ChangeDutyCycle(duty)


def stop_all_motors():
    """Stop every motor and reset all state variables to defaults."""
    global auger_active, auger_speed
    global platform_active, platform_speed, platform_direction
    global chamber_lid_active, chamber_lid_angle
    global soil_drop_active, soil_drop_angle

    # Send neutral signal to Spark MAX controllers (stops the NEO 550s)
    pwm_auger.ChangeDutyCycle(SPARK_NEUTRAL)
    pwm_platform.ChangeDutyCycle(SPARK_NEUTRAL)

    # Turn off servo PWM signals (servos will hold last position or relax)
    pwm_chamber_lid.ChangeDutyCycle(0)
    pwm_soil_drop.ChangeDutyCycle(0)

    # Reset state
    auger_active  = False
    auger_speed   = 0

    platform_active    = False
    platform_speed     = 0
    platform_direction = "up"

    chamber_lid_active = False
    chamber_lid_angle  = 0

    soil_drop_active = False
    soil_drop_angle  = 0




#####################################################################################################################
# CLI Display - Build the Text Shown in the Terminal
#   - Shows the current keybind controls at the top
#   - Shows the status of all four motors
#   - Highlights which motor is currently selected
#   - Shows the most recent action / message at the bottom
#####################################################################################################################

def build_display(msg):
    """Return a list of strings that make up the full terminal display."""

    # --- Selection indicator helper ---
    def sel(motor_num):
        return ">>>" if selected_motor == motor_num else "   "

    lines = []

    # Title
    lines.append("=" * 62)
    lines.append("   LUSI Science Module - Motor Controller")
    lines.append("=" * 62)
    lines.append("")

    # Keybind reference
    lines.append("  Keybind Controls:")
    lines.append("    1-4      Select a motor")
    lines.append("    ENTER    Start / activate the selected motor")
    lines.append("    UP/DOWN  Speed +/- 5%  (NEO 550 motors)")
    lines.append("             Angle +/- 1°  (Servo motors)")
    lines.append("    r        Reverse direction  (Platform motor only)")
    lines.append("    x        STOP all motors immediately")
    lines.append("    q        Quit program")
    lines.append("")

    # Divider
    lines.append("-" * 62)
    lines.append("")

    # Motor 1 - Auger
    status1  = "ON " if auger_active else "OFF"
    lines.append(f" {sel(1)}  [1] Auger Motor     (NEO 550)    "
                 f"| {status1} | Speed: {auger_speed:3d}%")

    # Motor 2 - Platform
    status2  = "ON " if platform_active else "OFF"
    dir_str  = platform_direction.upper() if platform_active else "--"
    lines.append(f" {sel(2)}  [2] Platform Motor  (NEO 550)    "
                 f"| {status2} | Speed: {platform_speed:3d}% | Dir: {dir_str}")

    # Motor 3 - Chamber Lid
    status3  = "ON " if chamber_lid_active else "OFF"
    lines.append(f" {sel(3)}  [3] Chamber Lid     (SM-S2309S)  "
                 f"| {status3} | Angle: {chamber_lid_angle:3d}°")

    # Motor 4 - Soil Dropper
    status4  = "ON " if soil_drop_active else "OFF"
    lines.append(f" {sel(4)}  [4] Soil Dropper    (SG92R)      "
                 f"| {status4} | Angle: {soil_drop_angle:3d}°")

    lines.append("")
    lines.append("-" * 62)
    lines.append(f"  >> {msg}")

    return "\n".join(lines)




#####################################################################################################################
# Main CLI Loop (runs inside curses)
#
#   How it works:
#       1. The terminal is cleared and redrawn every loop iteration
#       2. The program waits for a key press (non-blocking, checked every 100 ms)
#       3. Depending on the key, the program:
#           - Selects a motor (1–4)
#           - Activates the selected motor (Enter)
#           - Adjusts speed or angle (Up/Down arrow keys)
#           - Reverses the platform motor direction (r)
#           - Stops all motors (x)
#           - Quits the program (q)
#       4. After handling the key, the display is refreshed to show updated state
#####################################################################################################################

def main(stdscr):
    global selected_motor
    global auger_active, auger_speed
    global platform_active, platform_speed, platform_direction
    global chamber_lid_active, chamber_lid_angle
    global soil_drop_active, soil_drop_angle

    # Configure curses
    curses.curs_set(0)  # Hide the blinking cursor
    stdscr.nodelay(True)  # Don't block waiting for input - let us redraw the screen
    stdscr.keypad(True)  # Enable special keys like arrow keys

    msg = "Ready. Press 1-4 to select a motor."

    while True:
        # ---- Draw the screen ----
        stdscr.clear()
        stdscr.addstr(build_display(msg))
        stdscr.refresh()

        # ---- Read a key press ----
        key = stdscr.getch()

        # No key pressed - wait briefly and loop
        if key == -1:
            time.sleep(0.1)
            continue

        # ============================================================
        #  MOTOR SELECTION  (keys 1–4)
        # ============================================================
        if key == ord('1'):
            selected_motor = 1
            msg = "Selected: Auger Motor (NEO 550)"

        elif key == ord('2'):
            selected_motor = 2
            msg = "Selected: Platform Motor (NEO 550)"

        elif key == ord('3'):
            selected_motor = 3
            msg = "Selected: Chamber Lid Servo (SM-S2309S)"

        elif key == ord('4'):
            selected_motor = 4
            msg = "Selected: Soil Dropper Servo (SG92R)"

        # ============================================================
        #  ACTIVATE SELECTED MOTOR  (Enter key)
        # ============================================================
        elif key in (curses.KEY_ENTER, 10, 13):
            if selected_motor is None:
                msg = "No motor selected! Press 1-4 first."

            elif selected_motor == 1 and not auger_active:
                auger_active = True
                auger_speed  = 0
                set_spark_motor(pwm_auger, 0)
                msg = "Auger Motor ACTIVATED (speed 0%)"

            elif selected_motor == 2 and not platform_active:
                platform_active    = True
                platform_speed     = 0
                platform_direction = "up"
                set_spark_motor(pwm_platform, 0)
                msg = "Platform Motor ACTIVATED (speed 0%, direction UP)"

            elif selected_motor == 3 and not chamber_lid_active:
                chamber_lid_active = True
                chamber_lid_angle  = 0
                set_servo_angle(pwm_chamber_lid, 0)
                msg = "Chamber Lid Servo ACTIVATED (angle 0°)"

            elif selected_motor == 4 and not soil_drop_active:
                soil_drop_active = True
                soil_drop_angle  = 0
                set_servo_angle(pwm_soil_drop, 0)
                msg = "Soil Dropper Servo ACTIVATED (angle 0°)"

            else:
                msg = "That motor is already active."

        # ============================================================
        #  SPEED / ANGLE ADJUSTMENT  (Up and Down arrow keys)
        #   - Up   → increase speed (NEO 550) or angle (servo)
        #   - Down → decrease speed (NEO 550) or angle (servo)
        # ============================================================
        elif key == curses.KEY_UP:
            if selected_motor == 1 and auger_active:
                auger_speed = min(auger_speed + SPEED_STEP, 100)
                set_spark_motor(pwm_auger, auger_speed, "forward")
                msg = f"Auger speed → {auger_speed}%"

            elif selected_motor == 2 and platform_active:
                platform_speed = min(platform_speed + SPEED_STEP, 100)
                set_spark_motor(pwm_platform, platform_speed, platform_direction.replace("up", "forward").replace("down", "reverse"))
                msg = f"Platform speed → {platform_speed}% ({platform_direction})"

            elif selected_motor == 3 and chamber_lid_active:
                chamber_lid_angle = min(chamber_lid_angle + ANGLE_STEP, 180)
                set_servo_angle(pwm_chamber_lid, chamber_lid_angle)
                msg = f"Chamber Lid angle → {chamber_lid_angle}°"

            elif selected_motor == 4 and soil_drop_active:
                soil_drop_angle = min(soil_drop_angle + ANGLE_STEP, 180)
                set_servo_angle(pwm_soil_drop, soil_drop_angle)
                msg = f"Soil Dropper angle → {soil_drop_angle}°"

            else:
                msg = "Select and activate a motor first (1-4, then Enter)."

        elif key == curses.KEY_DOWN:
            if selected_motor == 1 and auger_active:
                auger_speed = max(auger_speed - SPEED_STEP, 0)
                set_spark_motor(pwm_auger, auger_speed, "forward")
                msg = f"Auger speed → {auger_speed}%"

            elif selected_motor == 2 and platform_active:
                platform_speed = max(platform_speed - SPEED_STEP, 0)
                set_spark_motor(pwm_platform, platform_speed, platform_direction.replace("up", "forward").replace("down", "reverse"))
                msg = f"Platform speed → {platform_speed}% ({platform_direction})"

            elif selected_motor == 3 and chamber_lid_active:
                chamber_lid_angle = max(chamber_lid_angle - ANGLE_STEP, 0)
                set_servo_angle(pwm_chamber_lid, chamber_lid_angle)
                msg = f"Chamber Lid angle → {chamber_lid_angle}°"

            elif selected_motor == 4 and soil_drop_active:
                soil_drop_angle = max(soil_drop_angle - ANGLE_STEP, 0)
                set_servo_angle(pwm_soil_drop, soil_drop_angle)
                msg = f"Soil Dropper angle → {soil_drop_angle}°"

            else:
                msg = "Select and activate a motor first (1-4, then Enter)."

        # ============================================================
        #  REVERSE DIRECTION  (r key - Platform motor only)
        # ============================================================
        elif key == ord('r'):
            if selected_motor == 2 and platform_active:
                # Flip the direction
                platform_direction = "down" if platform_direction == "up" else "up"
                # Apply the new direction at the current speed
                spark_dir = "forward" if platform_direction == "up" else "reverse"
                set_spark_motor(pwm_platform, platform_speed, spark_dir)
                msg = f"Platform direction → {platform_direction.upper()} (speed {platform_speed}%)"
            elif selected_motor == 1:
                msg = "Auger motor is forward-only (no reverse)."
            else:
                msg = "Reverse only works on the Platform motor (select 2)."

        # ============================================================
        #  EMERGENCY STOP  (x key - stops ALL motors immediately)
        # ============================================================
        elif key == ord('x'):
            stop_all_motors()
            msg = "ALL MOTORS STOPPED."

        # ============================================================
        #  QUIT PROGRAM  (q key)
        # ============================================================
        elif key == ord('q'):
            break

        # Small delay to prevent excessive CPU usage
        time.sleep(0.1)




#####################################################################################################################
# Main Execution and Cleanup
#   - curses.wrapper() runs the CLI and automatically restores the terminal on exit
#   - The "finally" block ensures all PWM signals are stopped and GPIO pins are released
#     even if the program crashes or is interrupted
#   - We send neutral (7.5%) to the Spark MAX controllers before stopping PWM
#     so the NEO 550 motors don't get an unexpected signal during shutdown
#####################################################################################################################

try:
    curses.wrapper(main)
finally:
    # Send neutral / off signals before shutting down
    pwm_auger.ChangeDutyCycle(SPARK_NEUTRAL)
    pwm_platform.ChangeDutyCycle(SPARK_NEUTRAL)
    pwm_chamber_lid.ChangeDutyCycle(0)
    pwm_soil_drop.ChangeDutyCycle(0)
    time.sleep(0.1)  # Brief pause to let the signals settle

    # Stop all PWM outputs
    pwm_auger.stop()
    pwm_platform.stop()
    pwm_chamber_lid.stop()
    pwm_soil_drop.stop()

    # Release PWM objects
    del pwm_auger
    del pwm_platform
    del pwm_chamber_lid
    del pwm_soil_drop

    # Release all GPIO pins back to the system
    GPIO.cleanup()
    print("All motors stopped. GPIO cleaned up safely.")