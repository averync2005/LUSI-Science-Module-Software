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
#   3. The program automatically calculates the correct PWM pulse width and applies it
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
#   - pigpio:
#       - Controls the Raspberry Pi's GPIO pins with hardware-timed PWM
#       - Unlike RPi.GPIO (which uses software-timed PWM), pigpio uses the Pi's
#         DMA (Direct Memory Access) hardware to generate precise pulse widths
#       - This is critical for servos, which need microsecond-accurate pulses
#         to translate commanded angles into actual shaft positions
#       - Requires the pigpio daemon to be running: sudo pigpiod
#####################################################################################################################

import time
import pigpio




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
# PWM Pulse Width Configuration (microseconds)
#   - pigpio controls motors by setting the pulse width directly in microseconds
#   - This is more precise than RPi.GPIO's duty-cycle percentages because pigpio
#     uses DMA hardware instead of software timers
#
# How the Spark MAX interprets the pulse width (NEO 550 motors):
#   - The Spark MAX reads the width of each pulse:
#       1000 µs --> full reverse
#       1500 µs --> neutral / stop
#       2000 µs --> full forward
#
# How standard servos interpret the pulse width:
#   - Pulse width maps to shaft angle:
#       500 µs --> 0°
#      1500 µs --> 90°
#      2500 µs --> 180°
#   - The formula used here: pulseWidth = 500 + (angle / 180) × 2000
#   - If your servo doesn't reach the full range, adjust SERVO_MIN_US and
#     SERVO_MAX_US until 0° and 180° match the physical positions
#####################################################################################################################

# Spark MAX pulse width boundaries (microseconds)
SPARK_NEUTRAL_US = 1500  # Motor stopped
SPARK_MAX_FWD_US = 2000  # Full speed forward
SPARK_MAX_REV_US = 1000  # Full speed reverse

# Servo pulse width boundaries (microseconds)
# Adjust these if your servos don't reach the full 0-180° range
SERVO_MIN_US = 500  # 0° position
SERVO_MAX_US = 2500  # 180° position




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
# pigpio Daemon Connection
#   - pigpio works by connecting to a daemon (background process) that controls
#     the GPIO pins using the Pi's DMA hardware
#   - The daemon must be started before running this script: sudo pigpiod
#   - pi.connected will be False if the daemon is not running
#####################################################################################################################

pi = pigpio.pi()  # Connect to the local pigpio daemon
if not pi.connected:
    print("[ERROR] Cannot connect to pigpio daemon. Start it with: sudo pigpiod")
    exit(1)




#####################################################################################################################
# Initializing Motor Signals
#   - Send the "off" signal to each motor pin on startup:
#       - Spark MAX motors get 1500 µs (neutral / stopped)
#       - Servos get 0 µs (no signal - holds last position or relaxes)
#   - pigpio.set_servo_pulsewidth() sends a 50 Hz PWM signal with the specified
#     pulse width in microseconds - this is the standard servo/ESC control method
#####################################################################################################################

pi.set_servo_pulsewidth(AUGER_PIN, SPARK_NEUTRAL_US)  # NEO 550 - start at neutral
pi.set_servo_pulsewidth(PLATFORM_PIN, SPARK_NEUTRAL_US)  # NEO 550 - start at neutral
pi.set_servo_pulsewidth(CHAMBER_LID_PIN, 0)  # Servo - signal off
pi.set_servo_pulsewidth(SOIL_DROP_PIN, 0)  # Servo - signal off




#####################################################################################################################
# Helper Function - Convert Speed % to Spark MAX Pulse Width
#
#   Parameters:
#       speedPct (int) - motor speed as a percentage, 0 to 100
#       direction (str) - "forward" or "reverse"
#
#   Returns:
#       int - the pulse width in microseconds to send to the Spark MAX
#
#   How it works:
#       Forward: pulseWidth = 1500 + (speed / 100) × 500 --> 1500 µs (stop) to 2000 µs (full forward)
#       Reverse: pulseWidth = 1500 - (speed / 100) × 500 --> 1500 µs (stop) to 1000 µs (full reverse)
#####################################################################################################################

def speedToPulseWidth(speedPct, direction="forward"):
    """Convert a speed percentage and direction to a Spark MAX pulse width in µs."""
    if direction == "forward":
        return SPARK_NEUTRAL_US + (speedPct / 100.0) * (SPARK_MAX_FWD_US - SPARK_NEUTRAL_US)
    else:
        return SPARK_NEUTRAL_US - (speedPct / 100.0) * (SPARK_NEUTRAL_US - SPARK_MAX_REV_US)




#####################################################################################################################
# Helper Function - Convert Angle to Servo Pulse Width
#
#   Parameters:
#       angle (int) - desired servo angle in degrees, 0 to 180
#
#   Returns:
#       int - the pulse width in microseconds to send to the servo
#
#   How it works:
#       pulseWidth = 500 + (angle / 180) × 2000
#       This maps 0° --> 500 µs, 90° --> 1500 µs, 180° --> 2500 µs
#####################################################################################################################

def angleToPulseWidth(angle):
    """Convert an angle in degrees to a servo pulse width in µs."""
    angle = max(0, min(180, angle))  # Clamp the angle to the valid range
    return SERVO_MIN_US + (angle / 180.0) * (SERVO_MAX_US - SERVO_MIN_US)




#####################################################################################################################
# Motor Control Functions
#   - setSparkMotor(): sends the correct pulse width to a Spark MAX (NEO 550)
#   - setServoAngle(): sends the correct pulse width to a hobby servo
#   - stopAllMotors(): immediately stops every motor and resets all state
#   - stopSingleMotor(): stops one motor by number and resets its state
#####################################################################################################################

def setSparkMotor(pin, speedPct, direction="forward"):
    """Send a speed command to a NEO 550 motor via its Spark MAX controller."""
    pulseWidth = speedToPulseWidth(speedPct, direction)
    pi.set_servo_pulsewidth(pin, pulseWidth)


def setServoAngle(pin, angle):
    """Move a servo motor to the specified angle (0-180°), then cut the signal to prevent jitter."""
    angle = max(0, min(180, angle))
    pulseWidth = angleToPulseWidth(angle)
    pi.set_servo_pulsewidth(pin, pulseWidth)
    time.sleep(0.5)  # Give the servo time to reach the target position
    pi.set_servo_pulsewidth(pin, 0)  # Cut the signal to stop jitter


def stopAllMotors():
    """Stop every motor and reset all state variables to defaults."""
    global augerActive, augerSpeed
    global platformActive, platformSpeed, platformDirection
    global chamberLidActive, chamberLidAngle
    global soilDropActive, soilDropAngle

    # Send neutral signal to Spark MAX controllers (stops the NEO 550s)
    pi.set_servo_pulsewidth(AUGER_PIN, SPARK_NEUTRAL_US)
    pi.set_servo_pulsewidth(PLATFORM_PIN, SPARK_NEUTRAL_US)

    # Turn off servo PWM signals (servos will hold last position or relax)
    pi.set_servo_pulsewidth(CHAMBER_LID_PIN, 0)
    pi.set_servo_pulsewidth(SOIL_DROP_PIN, 0)

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
        pi.set_servo_pulsewidth(AUGER_PIN, SPARK_NEUTRAL_US)
        augerActive = False
        augerSpeed = 0
        print("[INFO] Auger Motor stopped.")

    elif motorNum == 2:
        pi.set_servo_pulsewidth(PLATFORM_PIN, SPARK_NEUTRAL_US)
        platformActive = False
        platformSpeed = 0
        platformDirection = "up"
        print("[INFO] Platform Motor stopped.")

    elif motorNum == 3:
        pi.set_servo_pulsewidth(CHAMBER_LID_PIN, 0)
        chamberLidActive = False
        chamberLidAngle = 0
        print("[INFO] Chamber Lid Servo stopped.")

    elif motorNum == 4:
        pi.set_servo_pulsewidth(SOIL_DROP_PIN, 0)
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
        setSparkMotor(AUGER_PIN, augerSpeed, "forward")
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
        setSparkMotor(PLATFORM_PIN, platformSpeed, sparkDir)
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
        setServoAngle(CHAMBER_LID_PIN, chamberLidAngle)
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
        setServoAngle(SOIL_DROP_PIN, soilDropAngle)
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
#   - The "finally" block ensures all PWM signals are stopped and the pigpio
#     connection is released, even if the program crashes or is interrupted
#   - We send neutral (1500 µs) to the Spark MAX controllers before disconnecting
#     so the NEO 550 motors don't get an unexpected signal during shutdown
#####################################################################################################################

try:
    main()
finally:
    # Send neutral / off signals before shutting down
    pi.set_servo_pulsewidth(AUGER_PIN, SPARK_NEUTRAL_US)
    pi.set_servo_pulsewidth(PLATFORM_PIN, SPARK_NEUTRAL_US)
    pi.set_servo_pulsewidth(CHAMBER_LID_PIN, 0)
    pi.set_servo_pulsewidth(SOIL_DROP_PIN, 0)
    time.sleep(0.1)  # Brief pause to let the signals settle

    # Disconnect from the pigpio daemon and release all GPIO resources
    pi.stop()
    print("[INFO] All motors stopped. GPIO cleaned up safely.")
