#####################################################################################################################
# Importing Program Libraries
#   - cv2:
#       - Provides OpenCV’s camera access and video frame handling
#       - Enables reading live video streams from connected cameras
#       - Supports window display and keyboard event handling
#####################################################################################################################

import cv2





#####################################################################################################################
# Camera Initialization
#   - Attempts to connect to the external ELP USB camera
#   - Each connected camera is assigned an index number by the operating system
#   - Typically:
#       - Index 0: Built-in laptop webcam
#       - Index 1+: External USB cameras (ex. ELP USB camera)
#####################################################################################################################

cameraIndex = 1  # Change this value if the camera is detected at a different index
cameraCapture = cv2.VideoCapture(cameraIndex)  # Create a capture object for the specified camera index

if not cameraCapture.isOpened():
    print("Camera not detected. Try a different index or check the USB connection.")
    exit()  # Stop the program if the camera cannot be opened





#####################################################################################################################
# Camera Configuration
#   - Sets the preferred output resolution for the video stream
#   - Width and height values can be adjusted based on camera capability
#####################################################################################################################

cameraCapture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)   # Set horizontal resolution
cameraCapture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)   # Set vertical resolution

print("Press 'q' to quit the camera window")





#####################################################################################################################
# Live Camera Feed Loop
#   - Continuously reads frames from the camera
#   - Displays the live feed in a preview window
#   - Allows the user to quit by pressing the 'q' key
#####################################################################################################################

while True:
    success, capturedFrame = cameraCapture.read()  # Read one frame from the camera
    if not success:
        print("Failed to grab frame from camera")  # Display error if frame capture fails
        break

    cv2.imshow("ELP USB Camera", capturedFrame)  # Display the frame in a window titled "ELP USB Camera"

    # Wait for a key press for 1ms and check if 'q' is pressed to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break





#####################################################################################################################
# Program Cleanup
#   - Releases the camera device for future use
#   - Closes any OpenCV windows opened during the session
#####################################################################################################################

cameraCapture.release()  # Release the camera object
cv2.destroyAllWindows()  # Close any OpenCV display windows
print("Camera released and windows closed successfully.")