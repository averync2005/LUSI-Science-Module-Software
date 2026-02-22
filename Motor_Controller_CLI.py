#!/usr/bin/env python3
# This shebang line tells Linux and macOS to use Python 3 when the script is
# run directly from the terminal (e.g., ./Motor_Controller_CLI.py). On Windows,
# this line is ignored - you run scripts with "python Motor_Controller_CLI.py" instead.


#####################################################################################################################
# LUSI Science Module - Motor Controller CLI
#
# This script provides a menu-driven command-line interface for controlling the 4 motors on the LUSI Science Module.
# It runs on a Raspberry Pi and communicates over Ethernet to the base station computer.
#
# How the CLI works:
#   1. The command menu and motor list reprint before every prompt
#   2. Type a motor number (1-4) to select it and enter a speed or angle
#   3. The program automatically calculates the correct PWM duty cycle and applies it
#   4. Setting a NEO 550 motor to 0% speed automatically turns it off
#   5. Setting a servo to 0° moves it to the 0° position (resets the angle)
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
#     - Direction: forward (up) AND reverse (down) - prompted when selected
#   3. Testing Chamber Lid
#     - SM-S2309S servo
#     - Rotates the lid of the testing chamber
#     - Range: 0-180°
#   4. Soil Dropper
#     - SG92R micro servo
#     - Rotates a lid that drops collected soil
#     - Range: 0-180°
#####################################################################################################################




#####################################################################################################################
# Importing Program Libraries
#   - time:
#       - Adds small delays so the program doesn't hog the CPU
#       - Gives servos time to physically reach their target angle
#   - RPi.GPIO:
#       - Controls the Raspberry Pi's GPIO (General Purpose Input/Output) pins
#       - Configures pins as outputs so we can send PWM signals
#       - PWM (Pulse Width Modulation) signals tell the Spark MAX and servos what to do
#####################################################################################################################

import time
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




#####################################################################################################################
# Motor State Variables
#   - These keep track of whether each motor is active and its current speed/angle
#   - NEO 550 motors store speed as a percentage (0-100 %)
#   - Servos store angle in degrees (0-180°)
#   - Platform motor also stores its current direction ("up" or "down")
#   - A motor is "active" once you send it a command - it stays active until you
#     explicitly turn it off with "off <number>" or "stop"
#####################################################################################################################

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
#   - stopSingleMotor(): stops one motor by number and resets its state
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


def stopSingleMotor(motorNum):
    """Stop one motor by its number (1-4) and reset its state."""
    global augerActive, augerSpeed
    global platformActive, platformSpeed, platformDirection
    global chamberLidActive, chamberLidAngle
    global soilDropActive, soilDropAngle

    if motorNum == 1:
        pwmAuger.ChangeDutyCycle(SPARK_NEUTRAL)
        augerActive = False
        augerSpeed = 0
        print("[INFO] Auger Motor stopped.")

    elif motorNum == 2:
        pwmPlatform.ChangeDutyCycle(SPARK_NEUTRAL)
        platformActive = False
        platformSpeed = 0
        platformDirection = "up"
        print("[INFO] Platform Motor stopped.")

    elif motorNum == 3:
        pwmChamberLid.ChangeDutyCycle(0)
        chamberLidActive = False
        chamberLidAngle = 0
        print("[INFO] Chamber Lid Servo stopped.")

    elif motorNum == 4:
        pwmSoilDrop.ChangeDutyCycle(0)
        soilDropActive = False
        soilDropAngle = 0
        print("[INFO] Soil Dropper Servo stopped.")

    else:
        print("[WARN] Invalid motor number. Use 1-4.")




#####################################################################################################################
# Status Display
#   - Prints the current state of all four motors in a readable table
#   - Shows whether each motor is ON or OFF, its current speed/angle, and direction
#   - Called automatically after every command so you always see the latest state
#####################################################################################################################

def printStatus():
    """Print the current state of all four motors."""
    print("")
    print("=" * 62)
    print("  LUSI Science Module - Motor Status")
    print("=" * 62)

    # Motor 1 - Auger
    augerStatus = "ON" if augerActive else "OFF"
    augerLine = f"  [1] Auger Motor (NEO 550)    | {augerStatus} | Speed: {augerSpeed}%"
    print(augerLine)

    # Motor 2 - Platform
    platformStatus = "ON" if platformActive else "OFF"
    dirStr = platformDirection.upper() if platformActive else "--"
    platformLine = f"  [2] Platform Motor (NEO 550) | {platformStatus} | Speed: {platformSpeed}% | Dir: {dirStr}"
    print(platformLine)

    # Motor 3 - Chamber Lid
    chamberStatus = "ON" if chamberLidActive else "OFF"
    chamberLine = f"  [3] Chamber Lid (SM-S2309S)  | {chamberStatus} | Angle: {chamberLidAngle}°"
    print(chamberLine)

    # Motor 4 - Soil Dropper
    dropperStatus = "ON" if soilDropActive else "OFF"
    dropperLine = f"  [4] Soil Dropper (SG92R)     | {dropperStatus} | Angle: {soilDropAngle}°"
    print(dropperLine)

    print("=" * 62)
    print("")




#####################################################################################################################
# Command and Motor List Display
#   - Prints the available commands AND the numbered motor list together
#   - Reprinted every time the prompt comes back so the user always sees
#     what they can type
#   - The user types a motor number (1-4) directly to control it, or
#     types a utility command like stop, off, status, help, or q
#####################################################################################################################

def printMenu():
    """Print the commands and motor list."""
    print("-" * 62)
    print("  Commands:")
    print("    1-4          Select a motor (see list below)")
    print("    off          Turn off a single motor")
    print("    stop / x     Stop ALL motors immediately")
    print("    status / s   Show motor status")
    print("    help / h     Show this menu")
    print("    q            Quit program")
    print("-" * 62)
    print("  Motors:")
    print("    [1] Auger Motor (NEO 550)    - speed 0-100%, forward only")
    print("    [2] Platform Motor (NEO 550) - speed 0-100%, up or down")
    print("    [3] Chamber Lid (SM-S2309S)  - angle 0-180°")
    print("    [4] Soil Dropper (SG92R)     - angle 0-180°")
    print("")




#####################################################################################################################
# Handle Motor Selection - Set Speed or Angle for a Chosen Motor
#
#   How it works:
#       1. The user already typed a motor number (1-4) at the main prompt
#       2. Based on the motor selected:
#           - Motors 1 & 2 (NEO 550): asks for a speed percentage (0-100%)
#           - Motor 2 also asks for direction (up/down) before asking for speed
#           - Motors 3 & 4 (servos): asks for an angle in degrees (0-180°)
#       3. Setting 0% speed automatically turns that NEO 550 motor off
#       4. Setting 0° moves the servo to the 0° position (does NOT turn it off)
#       5. The PWM duty cycle is calculated automatically from the typed value
#
#   Parameters:
#       motorNum (int) - which motor was selected (1-4), passed from the main loop
#
#   Returns:
#       None - modifies global state variables and sends PWM signals
#####################################################################################################################

def handleMotorCommand(motorNum):
    """Prompt for speed or angle and apply it to the selected motor."""
    global augerActive, augerSpeed
    global platformActive, platformSpeed, platformDirection
    global chamberLidActive, chamberLidAngle
    global soilDropActive, soilDropAngle

    # ============================================================
    # Motor 1 - Auger (NEO 550, forward only)
    #   - Ask for speed 0-100%
    #   - 0% automatically turns the motor off
    # ============================================================
    if motorNum == 1:
        try:
            speedRaw = input("  Enter speed (0-100%): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        try:
            speed = int(speedRaw)
        except ValueError:
            print("[WARN] Speed must be a number 0-100.")
            return
        if speed < 0 or speed > 100:
            print("[WARN] Speed must be 0-100.")
            return

        # 0% means turn the motor off
        if speed == 0:
            stopSingleMotor(1)
            return

        augerActive = True
        augerSpeed = speed
        setSparkMotor(pwmAuger, augerSpeed, "forward")
        infoLine = f"[INFO] Auger speed set to {augerSpeed}%"
        print(infoLine)

    # ============================================================
    # Motor 2 - Platform (NEO 550, bidirectional)
    #   - Ask for direction (up/down) first
    #   - Then ask for speed 0-100%
    #   - 0% automatically turns the motor off
    # ============================================================
    elif motorNum == 2:
        try:
            dirRaw = input("  Direction (up/down): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        if dirRaw in ("up", "forward"):
            direction = "up"
        elif dirRaw in ("down", "reverse"):
            direction = "down"
        else:
            print("[WARN] Direction must be 'up' or 'down'.")
            return

        try:
            speedRaw = input("  Enter speed (0-100%): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        try:
            speed = int(speedRaw)
        except ValueError:
            print("[WARN] Speed must be a number 0-100.")
            return
        if speed < 0 or speed > 100:
            print("[WARN] Speed must be 0-100.")
            return

        # 0% means turn the motor off
        if speed == 0:
            stopSingleMotor(2)
            return

        platformActive = True
        platformSpeed = speed
        platformDirection = direction
        sparkDir = "forward" if platformDirection == "up" else "reverse"
        setSparkMotor(pwmPlatform, platformSpeed, sparkDir)
        infoLine = f"[INFO] Platform speed set to {platformSpeed}% ({platformDirection.upper()})"
        print(infoLine)

    # ============================================================
    # Motor 3 - Chamber Lid Servo (SM-S2309S)
    #   - Ask for angle 0-180°
    #   - 0° moves the servo to the 0° position (resets angle)
    # ============================================================
    elif motorNum == 3:
        try:
            angleRaw = input("  Enter angle (0-180°): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        try:
            angle = int(angleRaw)
        except ValueError:
            print("[WARN] Angle must be a number 0-180.")
            return
        if angle < 0 or angle > 180:
            print("[WARN] Angle must be 0-180.")
            return

        chamberLidActive = True
        chamberLidAngle = angle
        setServoAngle(pwmChamberLid, chamberLidAngle)
        infoLine = f"[INFO] Chamber Lid angle set to {chamberLidAngle}°"
        print(infoLine)

    # ============================================================
    # Motor 4 - Soil Dropper Servo (SG92R)
    #   - Ask for angle 0-180°
    #   - 0° moves the servo to the 0° position (resets angle)
    # ============================================================
    elif motorNum == 4:
        try:
            angleRaw = input("  Enter angle (0-180°): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        try:
            angle = int(angleRaw)
        except ValueError:
            print("[WARN] Angle must be a number 0-180.")
            return
        if angle < 0 or angle > 180:
            print("[WARN] Angle must be 0-180.")
            return

        soilDropActive = True
        soilDropAngle = angle
        setServoAngle(pwmSoilDrop, soilDropAngle)
        infoLine = f"[INFO] Soil Dropper angle set to {soilDropAngle}°"
        print(infoLine)




#####################################################################################################################
# Handle "off" Command - Turn Off a Single Motor
#
#   How it works:
#       1. Asks which motor to turn off (1-4)
#       2. Sends the appropriate stop signal (neutral for NEO 550, 0% for servos)
#       3. Resets the motor's state variables
#
#   Parameters:
#       None - reads input directly from the user via input()
#
#   Returns:
#       None - modifies global state variables and sends PWM signals
#####################################################################################################################

def handleOffCommand():
    """Ask which motor to turn off and stop it."""
    try:
        motorRaw = input("  Turn off motor (1-4): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return
    try:
        motorNum = int(motorRaw)
    except ValueError:
        print("[WARN] Please enter a number 1-4.")
        return
    stopSingleMotor(motorNum)




#####################################################################################################################
# Main CLI Loop
#
#   How it works:
#       1. On startup, prints the command menu, motor list, and status table
#       2. The menu and motor list reprint before every prompt so the user always
#          sees what they can type
#       3. The user types a motor number (1-4) to directly select and control it,
#          or types a utility command (off, stop, status, help, q)
#       4. After each command, the status table prints, then the menu reprints
#       5. The loop continues until the user types "q"
#       6. On exit (or crash), all PWM signals are stopped and GPIO pins are released
#####################################################################################################################

def main():
    """Run the main menu loop."""
    printStatus()

    while True:
        # Reprint the commands and motor list before every prompt
        printMenu()

        try:
            raw = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Handle CTRL+C or CTRL+D gracefully
            print("")
            break

        # Skip empty input
        if not raw:
            continue

        cmd = raw.lower()

        # ============================================================
        # QUIT (q)
        # ============================================================
        if cmd == "q":
            break

        # ============================================================
        # HELP (help, h)
        # ============================================================
        elif cmd in ("help", "h"):
            continue  # Menu reprints at top of loop

        # ============================================================
        # STATUS (status, s)
        # ============================================================
        elif cmd in ("status", "s"):
            printStatus()
            continue  # Already printing status

        # ============================================================
        # MOTOR SELECTION (1-4)
        #   - Type a motor number to jump straight into setting it
        # ============================================================
        elif cmd in ("1", "2", "3", "4"):
            handleMotorCommand(int(cmd))

        # ============================================================
        # OFF - Turn off a single motor
        # ============================================================
        elif cmd == "off":
            handleOffCommand()

        # ============================================================
        # STOP ALL MOTORS (stop, x)
        # ============================================================
        elif cmd in ("stop", "x"):
            stopAllMotors()
            print("[INFO] ALL MOTORS STOPPED.")

        # ============================================================
        # UNKNOWN COMMAND
        # ============================================================
        else:
            unknownLine = f"[WARN] Unknown command: '{raw}'. Type 'help' for available commands."
            print(unknownLine)
            continue  # Don't print status for unknown commands

        # Print updated status after every successful command
        printStatus()




#####################################################################################################################
# Main Execution and Cleanup
#   - Runs the main CLI loop
#   - The "finally" block ensures all PWM signals are stopped and GPIO pins are released
#     even if the program crashes or is interrupted
#   - We send neutral (7.5%) to the Spark MAX controllers before stopping PWM
#     so the NEO 550 motors don't get an unexpected signal during shutdown
#####################################################################################################################

try:
    main()
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
