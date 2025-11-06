#####################################################################################################################
# Importing Program Libraries
#   - argparse:
#       - Handles command-line argument parsing for user configuration
#   - json:
#       - Saves image metadata as JSON sidecar files
#   - os:
#       - Handles directory creation and file path management
#   - time:
#       - Tracks frame timing and FPS estimation
#   - datetime:
#       - Generates ISO timestamps for saved images and videos
#   - cv2:
#       - Provides OpenCV functions for camera control, display, and recording
#####################################################################################################################

import argparse
import json
import os
import time
from datetime import datetime, timezone
import cv2





#####################################################################################################################
# Argument Parser
#   - Handles user input for camera index, resolution, FPS, and recording options
#   - Allows control over overlays such as grid and histogram
#   - Provides options to adjust exposure, gain, and backend configuration
#####################################################################################################################

def parseArgs():
    parser = argparse.ArgumentParser(
        description="ELP camera live preview with capture/record overlays",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--index", type=int, default=1, help="Camera index to open")
    parser.add_argument("--width", type=int, default=1280, help="Requested frame width")
    parser.add_argument("--height", type=int, default=720, help="Requested frame height")
    parser.add_argument("--fps", type=float, default=30.0, help="Requested FPS; 0 to skip setting FPS")
    parser.add_argument("--codec", type=str, default="MJPG", help="FourCC video codec for recording")
    parser.add_argument("--saveDir", type=str, default="captures", help="Directory for saved images and videos")
    parser.add_argument("--record", type=str, default=None, help="Start recording to this file path")
    parser.add_argument("--grid", action="store_true", help="Start with thirds grid overlay")
    parser.add_argument("--hist", action="store_true", help="Start with histogram overlay")
    parser.add_argument("--noDshow", action="store_true", help="Do not force DirectShow backend on Windows")
    parser.add_argument("--exposure", type=float, default=None, help="Set exposure value if supported")
    parser.add_argument("--gain", type=float, default=None, help="Set gain value if supported")

    return parser.parse_args()





#####################################################################################################################
# Camera Initialization
#   - Opens the camera at the specified index
#   - Uses DirectShow backend on Windows if available for better device access
#####################################################################################################################

def openCamera(index: int, useDshow: bool):
    backend = cv2.CAP_DSHOW if (os.name == "nt" and useDshow) else 0
    cameraCapture = cv2.VideoCapture(index, backend)

    if not cameraCapture.isOpened() and backend == cv2.CAP_DSHOW:
        cameraCapture = cv2.VideoCapture(index)

    return cameraCapture





#####################################################################################################################
# Directory Management
#   - Ensures the save directory exists before writing files
#####################################################################################################################

def ensureDir(path: str):
    os.makedirs(path, exist_ok=True)





#####################################################################################################################
# Grid Overlay Function
#   - Draws rule-of-thirds gridlines on the video feed
#####################################################################################################################

def drawGrid(frame):
    height, width = frame.shape[:2]
    color = (0, 255, 0)
    thickness = 1
    thirdW = width // 3
    thirdH = height // 3

    for x in (thirdW, 2 * thirdW):
        cv2.line(frame, (x, 0), (x, height - 1), color, thickness)

    for y in (thirdH, 2 * thirdH):
        cv2.line(frame, (0, y), (width - 1, y), color, thickness)





#####################################################################################################################
# Histogram Overlay Function
#   - Calculates grayscale histogram and overlays it in the top-left corner
#####################################################################################################################

def drawHistogram(frame):
    import numpy as np  # Lazy import so numpy is only required when histogram overlay is enabled

    grayFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    histValues = cv2.calcHist([grayFrame], [0], None, [64], [0, 256])
    cv2.normalize(histValues, histValues, 0, 100, cv2.NORM_MINMAX)
    histValues = histValues.flatten()

    width, height = 128, 100
    histImage = 255 * np.ones((height, width, 3), dtype="uint8")
    step = width / len(histValues)

    for i, value in enumerate(histValues):
        x = int(i * step)
        y = int(value)
        cv2.line(histImage, (x, height), (x, height - y), (0, 0, 0), 1)

    frame[5 : 5 + height, 5 : 5 + width] = cv2.addWeighted(
        frame[5 : 5 + height, 5 : 5 + width], 0.6, histImage, 0.4, 0
    )





#####################################################################################################################
# Overlay Text Function
#   - Displays status messages or controls on the video frame
#####################################################################################################################

def putOverlay(frame, text, y=20):
    cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)





#####################################################################################################################
# Timestamp Function
#   - Returns current UTC time in ISO 8601 format
#####################################################################################################################

def nowUtcIso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")





#####################################################################################################################
# Metadata Writer
#   - Saves image capture metadata as a JSON sidecar file
#####################################################################################################################

def sidecarMetadata(pathPng: str, metadata: dict):
    metadataPath = os.path.splitext(pathPng)[0] + ".json"
    with open(metadataPath, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)





#####################################################################################################################
# Main Execution
#   - Handles live preview, capture, and recording logic
#   - Supports grid/histogram overlays and metadata generation
#####################################################################################################################

def main():
    args = parseArgs()
    ensureDir(args.saveDir)

    cameraCapture = openCamera(args.index, useDshow=not args.noDshow)
    if not cameraCapture.isOpened():
        print("Camera not detected. Try a different index or check the USB connection.")
        return

    # Configure camera properties
    cameraCapture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if args.width > 0:
        cameraCapture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height > 0:
        cameraCapture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if args.fps > 0:
        cameraCapture.set(cv2.CAP_PROP_FPS, args.fps)
    if args.exposure is not None:
        cameraCapture.set(cv2.CAP_PROP_EXPOSURE, args.exposure)
    if args.gain is not None:
        cameraCapture.set(cv2.CAP_PROP_GAIN, args.gain)

    actualWidth = int(cameraCapture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actualHeight = int(cameraCapture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    nominalFps = cameraCapture.get(cv2.CAP_PROP_FPS) or args.fps or 0

    # Setup recording parameters
    fourcc = cv2.VideoWriter_fourcc(*args.codec)
    isRecording = False
    videoWriter = None
    pendingRecordPath = args.record if args.record else None

    showGrid = args.grid
    showHist = args.hist

    windowName = "ELP USB Camera"
    cv2.namedWindow(windowName, cv2.WINDOW_NORMAL)

    # FPS tracking variables
    fpsEma = 0.0
    alpha = 0.2
    lastTime = time.perf_counter()

    print("Hotkeys: q quit | c capture | r record | g grid | h hist")

    while True:
        success, frame = cameraCapture.read()
        if not success or frame is None:
            print("Failed to grab frame from camera")
            break

        if frame.shape[1] != actualWidth or frame.shape[0] != actualHeight:
            actualWidth = frame.shape[1]
            actualHeight = frame.shape[0]

        if showGrid:
            drawGrid(frame)
        if showHist:
            try:
                drawHistogram(frame)
            except Exception:
                pass

        # Calculate FPS
        currentTime = time.perf_counter()
        deltaTime = currentTime - lastTime
        lastTime = currentTime
        instantFps = (1.0 / deltaTime) if deltaTime > 0 else 0.0
        fpsEma = instantFps if fpsEma == 0 else (alpha * instantFps + (1 - alpha) * fpsEma)

        # Overlays
        putOverlay(frame, f"{actualWidth}x{actualHeight} | FPS: {fpsEma:4.1f}")
        putOverlay(frame, "[c] Capture  [r] Record  [g] Grid  [h] Hist  [q] Quit", y=40)

        # Start recording if requested
        if pendingRecordPath and videoWriter is None:
            outputPath = pendingRecordPath
            if not os.path.isabs(outputPath):
                outputPath = os.path.join(args.saveDir, outputPath)
            ensureDir(os.path.dirname(outputPath) or ".")
            videoFps = nominalFps if nominalFps and nominalFps > 0 else max(1.0, fpsEma)
            videoWriter = cv2.VideoWriter(outputPath, fourcc, videoFps, (actualWidth, actualHeight))
            isRecording = videoWriter.isOpened()
            print(f"Recording started -> {outputPath}" if isRecording else "Failed to start recording")
            pendingRecordPath = None

        # Write frames while recording
        if isRecording and videoWriter is not None and videoWriter.isOpened():
            videoWriter.write(frame)

        cv2.imshow(windowName, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("g"):
            showGrid = not showGrid
        elif key == ord("h"):
            showHist = not showHist
        elif key == ord("c"):
            timestamp = nowUtcIso()
            baseName = f"IMG_{timestamp}_{actualWidth}x{actualHeight}"
            imagePath = os.path.join(args.saveDir, baseName + ".png")
            cv2.imwrite(imagePath, frame)
            metadata = {
                "timestamp_utc": timestamp,
                "camera_index": args.index,
                "frame_width": actualWidth,
                "frame_height": actualHeight,
                "requested_fps": args.fps,
                "measured_fps": round(fpsEma, 2),
                "exposure": cameraCapture.get(cv2.CAP_PROP_EXPOSURE),
                "gain": cameraCapture.get(cv2.CAP_PROP_GAIN),
                "codec": args.codec,
                "software": "ELP_Camera.py",
            }
            sidecarMetadata(imagePath, metadata)
            print(f"Saved still -> {imagePath}")
        elif key == ord("r"):
            if isRecording and videoWriter is not None:
                videoWriter.release()
                isRecording = False
                print("Recording stopped")
            else:
                timestamp = nowUtcIso()
                videoName = f"VID_{timestamp}_{actualWidth}x{actualHeight}.avi"
                pendingRecordPath = os.path.join(args.saveDir, videoName)

        if cv2.getWindowProperty(windowName, cv2.WND_PROP_VISIBLE) < 1:
            break

    if videoWriter is not None and videoWriter.isOpened():
        videoWriter.release()
    cameraCapture.release()
    cv2.destroyAllWindows()
    print("Camera released and windows closed successfully.")





#####################################################################################################################
# Program Entry Point
#   - Executes main() only when the script is run directly
#####################################################################################################################

if __name__ == "__main__":
    main()