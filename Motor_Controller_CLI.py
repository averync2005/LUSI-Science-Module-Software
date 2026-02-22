#!/usr/bin/env python3
# This shebang line tells Linux and macOS to use Python 3 when the script is
# run directly from the terminal (e.g., ./Motor_Controller_CLI.py). On Windows,
# this line is ignored - you run scripts with "python Motor_Controller_CLI.py" instead.


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
#     - Range: 0-180°, ±1° fine control
#   4. Soil Dropper
#     - SG92R micro servo
#     - Rotates a lid that drops collected soil
#     - Range: 0-180°, ±1° fine control
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

AUGER_PIN = 12  # NEO 550 --> Spark MAX controller --> GPIO 12
PLATFORM_PIN = 13  # NEO 550 --> Spark MAX controller --> GPIO 13
CHAMBER_LID_PIN = 18  # SM-S2309S servo --> GPIO 18
SOIL_DROP_PIN = 19  # SG92R micro servo --> GPIO 19




#####################################################################################################################
# PWM Configuration
#   - All four motors use 50 Hz PWM (one pulse every 20 ms)
#   - 50 Hz is the standard for both hobby servos and the REV Spark MAX
#
# How the Spark MAX interprets the PWM signal (NEO 550 motors):
#   - The Spark MAX reads the width of each pulse (in microseconds):
#       1000 µs --> full reverse
#       1500 µs --> neutral / stop
#       2000 µs --> full forward
#   - At 50 Hz the period is 20 000 µs, so duty-cycle percentages are:
#       5.0 % --> 1000 µs --> full reverse
#       7.5 % --> 1500 µs --> neutral
#      10.0 % --> 2000 µs --> full forward
#
# How standard servos interpret the PWM signal:
#   - Pulse width maps to shaft angle:
#       ~500 µs (2.5 %) --> 0°
#      ~1500 µs (7.5 %) --> 90°
#      ~2500 µs (12.5 %) --> 180°
#   - The formula used here: duty% = (angle / 18) + 2.5
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
#   - "selectedMotor" tracks which motor the user is currently controlling (1-4)
#   - NEO 550 motors store speed as a percentage (0-100 %)
#   - Servos store angle in degrees (0-180°)
#   - Platform motor also stores its current direction ("up" or "down")
#####################################################################################################################

selectedMotor = None  # Which motor is currently selected (1, 2, 3, or 4)

# Motor 1 - Auger (forward only)
augerActive = False
augerSpeed = 0  # 0-100 %

# Motor 2 - Platform (bidirectional)
platformActive = False
platformSpeed = 0  # 0-100 %
platformDirection = "up"  # "up" (forward) or "down" (reverse)

# Motor 3 - Chamber lid servo
chamberLidActive = False
chamberLidAngle = 0  # 0-180°

# Motor 4 - Soil dropper servo
soilDropActive = False
soilDropAngle = 0  # 0-180°




#####################################################################################################################
# GPIO Setup
#   - Tell the Pi we are using BCM pin numbering
#   - Configure each motor pin as an output (we send signals OUT to the motors)
#####################################################################################################################

GPIO.setmode(GPIO.BCM)
GPIO.setup(AUGER_PIN, GPIO.OUT)
GPIO.setup(PLATFORM_PIN, GPIO.OUT)
GPIO.setup(CHAMBER_LID_PIN, GPIO.OUT)
GPIO.setup(SOIL_DROP_PIN, GPIO.OUT)




#####################################################################################################################
# Initializing PWM Objects
#   - Create a PWM object for each motor pin at 50 Hz
#   - Start each PWM output at the appropriate "off" duty cycle:
#       - Spark MAX motors start at 7.5 % (neutral / stopped)
#       - Servos start at 0 % (signal off - holds last position or relaxes)
#####################################################################################################################

pwmAuger = GPIO.PWM(AUGER_PIN, PWM_FREQUENCY)
pwmPlatform = GPIO.PWM(PLATFORM_PIN, PWM_FREQUENCY)
pwmChamberLid = GPIO.PWM(CHAMBER_LID_PIN, PWM_FREQUENCY)
pwmSoilDrop = GPIO.PWM(SOIL_DROP_PIN, PWM_FREQUENCY)

pwmAuger.start(SPARK_NEUTRAL)  # NEO 550 - start at neutral
pwmPlatform.start(SPARK_NEUTRAL)  # NEO 550 - start at neutral
pwmChamberLid.start(0)  # Servo - signal off
pwmSoilDrop.start(0)  # Servo - signal off




#####################################################################################################################
# Helper Function - Convert Speed % to Spark MAX Duty Cycle
#
#   Parameters:
#       speedPct (int) - motor speed as a percentage, 0 to 100
#       direction (str) - "forward" or "reverse"
#
#   Returns:
#       float - the PWM duty-cycle percentage to send to the Spark MAX
#
#   How it works:
#       Forward: duty = 7.5 + (speed / 100) × 2.5 --> 7.5 % (stop) to 10.0 % (full forward)
#       Reverse: duty = 7.5 - (speed / 100) × 2.5 --> 7.5 % (stop) to 5.0 % (full reverse)
#####################################################################################################################

def speedToSparkDuty(speedPct, direction="forward"):
    """Convert a speed percentage and direction to a Spark MAX duty-cycle value."""
    if direction == "forward":
        return SPARK_NEUTRAL + (speedPct / 100.0) * (SPARK_MAX_FWD - SPARK_NEUTRAL)
    else:
        return SPARK_NEUTRAL - (speedPct / 100.0) * (SPARK_NEUTRAL - SPARK_MAX_REV)




#####################################################################################################################
# Helper Function - Convert Angle to Servo Duty Cycle
#
#   Parameters:
#       angle (int) - desired servo angle in degrees, 0 to 180
#
#   Returns:
#       float - the PWM duty-cycle percentage to send to the servo
#
#   How it works:
#       duty = (angle / 18) + 2.5
#       This maps 0° --> 2.5 %, 90° --> 7.5 %, 180° --> 12.5 %
#####################################################################################################################

def angleToServoDuty(angle):
    """Convert an angle in degrees to a servo PWM duty-cycle value."""
    angle = max(0, min(180, angle))  # Clamp the angle to the valid range
    return (angle / 18.0) + 2.5




#####################################################################################################################
# Motor Control Functions
#   - setSparkMotor(): sends the correct duty cycle to a Spark MAX (NEO 550)
#   - setServoAngle(): sends the correct duty cycle to a hobby servo
#   - stopAllMotors(): immediately stops every motor and resets all state
#####################################################################################################################

def setSparkMotor(pwmObj, speedPct, direction="forward"):
    """Send a speed command to a NEO 550 motor via its Spark MAX controller."""
    duty = speedToSparkDuty(speedPct, direction)
    pwmObj.ChangeDutyCycle(duty)


def setServoAngle(pwmObj, angle):
    """Move a servo motor to the specified angle (0-180°)."""
    angle = max(0, min(180, angle))
    duty = angleToServoDuty(angle)
    pwmObj.ChangeDutyCycle(duty)


def stopAllMotors():
    """Stop every motor and reset all state variables to defaults."""
    global augerActive, augerSpeed
    global platformActive, platformSpeed, platformDirection
    global chamberLidActive, chamberLidAngle
    global soilDropActive, soilDropAngle

    # Send neutral signal to Spark MAX controllers (stops the NEO 550s)
    pwmAuger.ChangeDutyCycle(SPARK_NEUTRAL)
    pwmPlatform.ChangeDutyCycle(SPARK_NEUTRAL)

    # Turn off servo PWM signals (servos will hold last position or relax)
    pwmChamberLid.ChangeDutyCycle(0)
    pwmSoilDrop.ChangeDutyCycle(0)

    # Reset state
    augerActive = False
    augerSpeed = 0

    platformActive = False
    platformSpeed = 0
    platformDirection = "up"

    chamberLidActive = False
    chamberLidAngle = 0

    soilDropActive = False
    soilDropAngle = 0




#####################################################################################################################
# CLI Display - Build the Text Shown in the Terminal
#   - Shows the current keybind controls at the top
#   - Shows the status of all four motors
#   - Highlights which motor is currently selected with ">>>"
#   - Shows the most recent action / message at the bottom
#####################################################################################################################

def buildDisplay(msg):
    """Return a single string that makes up the full terminal display."""

    # Selection indicator helper
    def sel(motorNum):
        return ">>>" if selectedMotor == motorNum else "   "

    lines = []

    # Title
    lines.append("=" * 62)
    lines.append("  LUSI Science Module - Motor Controller")
    lines.append("=" * 62)
    lines.append("")

    # Keybind reference
    lines.append("  Keybind Controls:")
    lines.append("    1-4     Select a motor")
    lines.append("    ENTER   Start / activate the selected motor")
    lines.append("    UP/DOWN Speed +/- 5% (NEO 550) / Angle +/- 1° (Servos)")
    lines.append("    r       Reverse direction (Platform motor only)")
    lines.append("    x       STOP all motors immediately")
    lines.append("    q       Quit program")
    lines.append("")

    # Divider
    lines.append("-" * 62)
    lines.append("")

    # Motor 1 - Auger
    augerStatus = "ON" if augerActive else "OFF"
    augerLine = f"{sel(1)} [1] Auger Motor (NEO 550) | {augerStatus} | Speed: {augerSpeed:3d}%"
    lines.append(augerLine)

    # Motor 2 - Platform
    platformStatus = "ON" if platformActive else "OFF"
    dirStr = platformDirection.upper() if platformActive else "--"
    platformLine = f"{sel(2)} [2] Platform Motor (NEO 550) | {platformStatus} | Speed: {platformSpeed:3d}% | Dir: {dirStr}"
    lines.append(platformLine)

    # Motor 3 - Chamber Lid
    chamberStatus = "ON" if chamberLidActive else "OFF"
    chamberLine = f"{sel(3)} [3] Chamber Lid (SM-S2309S) | {chamberStatus} | Angle: {chamberLidAngle:3d}°"
    lines.append(chamberLine)

    # Motor 4 - Soil Dropper
    dropperStatus = "ON" if soilDropActive else "OFF"
    dropperLine = f"{sel(4)} [4] Soil Dropper (SG92R) | {dropperStatus} | Angle: {soilDropAngle:3d}°"
    lines.append(dropperLine)

    lines.append("")
    lines.append("-" * 62)
    msgLine = f">> {msg}"
    lines.append(msgLine)

    return "\n".join(lines)




#####################################################################################################################
# Main CLI Loop (runs inside curses)
#
#   How it works:
#       1. The terminal is cleared and redrawn every loop iteration
#       2. The program waits for a key press (non-blocking, checked every 100 ms)
#       3. Depending on the key, the program:
#           - Selects a motor (1-4)
#           - Activates the selected motor (Enter)
#           - Adjusts speed or angle (Up/Down arrow keys)
#           - Reverses the platform motor direction (r)
#           - Stops all motors (x)
#           - Quits the program (q)
#       4. After handling the key, the display is refreshed to show updated state
#####################################################################################################################

def main(stdscr):
    global selectedMotor
    global augerActive, augerSpeed
    global platformActive, platformSpeed, platformDirection
    global chamberLidActive, chamberLidAngle
    global soilDropActive, soilDropAngle

    # Configure curses
    curses.curs_set(0)  # Hide the blinking cursor
    stdscr.nodelay(True)  # Don't block waiting for input - let us redraw the screen
    stdscr.keypad(True)  # Enable special keys like arrow keys

    msg = "Ready. Press 1-4 to select a motor."

    while True:
        # ---- Draw the screen ----
        stdscr.clear()
        stdscr.addstr(buildDisplay(msg))
        stdscr.refresh()

        # ---- Read a key press ----
        key = stdscr.getch()

        # No key pressed - wait briefly and loop
        if key == -1:
            time.sleep(0.1)
            continue

        # ============================================================
        # MOTOR SELECTION (keys 1-4)
        # ============================================================
        if key == ord('1'):
            selectedMotor = 1
            msg = "Selected: Auger Motor (NEO 550)"

        elif key == ord('2'):
            selectedMotor = 2
            msg = "Selected: Platform Motor (NEO 550)"

        elif key == ord('3'):
            selectedMotor = 3
            msg = "Selected: Chamber Lid Servo (SM-S2309S)"

        elif key == ord('4'):
            selectedMotor = 4
            msg = "Selected: Soil Dropper Servo (SG92R)"

        # ============================================================
        # ACTIVATE SELECTED MOTOR (Enter key)
        # ============================================================
        elif key in (curses.KEY_ENTER, 10, 13):
            if selectedMotor is None:
                msg = "[WARN] No motor selected! Press 1-4 first."

            elif selectedMotor == 1 and not augerActive:
                augerActive = True
                augerSpeed = 0
                setSparkMotor(pwmAuger, 0)
                msg = "[INFO] Auger Motor ACTIVATED (speed 0%)"

            elif selectedMotor == 2 and not platformActive:
                platformActive = True
                platformSpeed = 0
                platformDirection = "up"
                setSparkMotor(pwmPlatform, 0)
                msg = "[INFO] Platform Motor ACTIVATED (speed 0%, direction UP)"

            elif selectedMotor == 3 and not chamberLidActive:
                chamberLidActive = True
                chamberLidAngle = 0
                setServoAngle(pwmChamberLid, 0)
                msg = "[INFO] Chamber Lid Servo ACTIVATED (angle 0°)"

            elif selectedMotor == 4 and not soilDropActive:
                soilDropActive = True
                soilDropAngle = 0
                setServoAngle(pwmSoilDrop, 0)
                msg = "[INFO] Soil Dropper Servo ACTIVATED (angle 0°)"

            else:
                msg = "[WARN] That motor is already active."

        # ============================================================
        # SPEED / ANGLE ADJUSTMENT (Up and Down arrow keys)
        #   - Up --> increase speed (NEO 550) or angle (servo)
        #   - Down --> decrease speed (NEO 550) or angle (servo)
        # ============================================================
        elif key == curses.KEY_UP:
            if selectedMotor == 1 and augerActive:
                augerSpeed = min(augerSpeed + SPEED_STEP, 100)
                setSparkMotor(pwmAuger, augerSpeed, "forward")
                msg = f"Auger speed: {augerSpeed}%"

            elif selectedMotor == 2 and platformActive:
                platformSpeed = min(platformSpeed + SPEED_STEP, 100)
                setSparkMotor(pwmPlatform, platformSpeed, platformDirection.replace("up", "forward").replace("down", "reverse"))
                msg = f"Platform speed: {platformSpeed}% ({platformDirection})"

            elif selectedMotor == 3 and chamberLidActive:
                chamberLidAngle = min(chamberLidAngle + ANGLE_STEP, 180)
                setServoAngle(pwmChamberLid, chamberLidAngle)
                msg = f"Chamber Lid angle: {chamberLidAngle}°"

            elif selectedMotor == 4 and soilDropActive:
                soilDropAngle = min(soilDropAngle + ANGLE_STEP, 180)
                setServoAngle(pwmSoilDrop, soilDropAngle)
                msg = f"Soil Dropper angle: {soilDropAngle}°"

            else:
                msg = "[WARN] Select and activate a motor first (1-4, then Enter)."

        elif key == curses.KEY_DOWN:
            if selectedMotor == 1 and augerActive:
                augerSpeed = max(augerSpeed - SPEED_STEP, 0)
                setSparkMotor(pwmAuger, augerSpeed, "forward")
                msg = f"Auger speed: {augerSpeed}%"

            elif selectedMotor == 2 and platformActive:
                platformSpeed = max(platformSpeed - SPEED_STEP, 0)
                setSparkMotor(pwmPlatform, platformSpeed, platformDirection.replace("up", "forward").replace("down", "reverse"))
                msg = f"Platform speed: {platformSpeed}% ({platformDirection})"

            elif selectedMotor == 3 and chamberLidActive:
                chamberLidAngle = max(chamberLidAngle - ANGLE_STEP, 0)
                setServoAngle(pwmChamberLid, chamberLidAngle)
                msg = f"Chamber Lid angle: {chamberLidAngle}°"

            elif selectedMotor == 4 and soilDropActive:
                soilDropAngle = max(soilDropAngle - ANGLE_STEP, 0)
                setServoAngle(pwmSoilDrop, soilDropAngle)
                msg = f"Soil Dropper angle: {soilDropAngle}°"

            else:
                msg = "[WARN] Select and activate a motor first (1-4, then Enter)."

        # ============================================================
        # REVERSE DIRECTION (r key - Platform motor only)
        # ============================================================
        elif key == ord('r'):
            if selectedMotor == 2 and platformActive:
                # Flip the direction
                platformDirection = "down" if platformDirection == "up" else "up"
                # Apply the new direction at the current speed
                sparkDir = "forward" if platformDirection == "up" else "reverse"
                setSparkMotor(pwmPlatform, platformSpeed, sparkDir)
                msg = f"Platform direction: {platformDirection.upper()} (speed {platformSpeed}%)"
            elif selectedMotor == 1:
                msg = "[WARN] Auger motor is forward-only (no reverse)."
            else:
                msg = "[WARN] Reverse only works on the Platform motor (select 2)."

        # ============================================================
        # EMERGENCY STOP (x key - stops ALL motors immediately)
        # ============================================================
        elif key == ord('x'):
            stopAllMotors()
            msg = "[INFO] ALL MOTORS STOPPED."

        # ============================================================
        # QUIT PROGRAM (q key)
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
    pwmAuger.ChangeDutyCycle(SPARK_NEUTRAL)
    pwmPlatform.ChangeDutyCycle(SPARK_NEUTRAL)
    pwmChamberLid.ChangeDutyCycle(0)
    pwmSoilDrop.ChangeDutyCycle(0)
    time.sleep(0.1)  # Brief pause to let the signals settle

    # Stop all PWM outputs
    pwmAuger.stop()
    pwmPlatform.stop()
    pwmChamberLid.stop()
    pwmSoilDrop.stop()

    # Release PWM objects
    del pwmAuger
    del pwmPlatform
    del pwmChamberLid
    del pwmSoilDrop

    # Release all GPIO pins back to the system
    GPIO.cleanup()
    print("[INFO] All motors stopped. GPIO cleaned up safely.")
