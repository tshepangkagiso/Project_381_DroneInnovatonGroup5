This application is a wildlife monitoring drone system with the following key capabilities:

1. Drone Control & Video:
```
    - Connect to DJI Tello drone
    - Real-time video streaming
    - Dual video feeds:
        * Raw feed from drone
        * Detection feed with threat highlights
    - Battery monitoring
    - Emergency return capabilities
```

2. Threat Detection System:
```
    - Real-time object detection using YOLO model
    - Detects multiple threat levels:
        * High Threat: Big cats, armed persons
        * Medium Threat: Wildlife (elephants, bears, etc.)
        * Low Threat: Normal activity
        * Livestock Monitoring
    - Saves detected threats with:
        * Timestamped images
        * Location data
        * Confidence scores
        * JSON metadata
```

3. Patrol System:
```
    - Two Patrol Modes:
        a) Square Patrol:
            - User sets single length for square perimeter
            - Drone patrols square corners systematically
            - Starts from bottom right corner
        
        b) Random Patrol:
            - Generates random points within square
            - Number of points based on battery level:
                * Battery > 75%: 3 points
                * Battery < 75%: 1 point

    - Height Control:
        - User-configurable fixed height (1-30 meters)
        - Maintains consistent altitude during patrol
```

4. Scanning & Detection:
```
    - At Each Point:
        - Performs 360° scan
        - Real-time threat detection
        - Video analysis and classification
        - Immediate alert system
```

5. Alert & Monitoring:
``` 
    - Real-time alerts for:
        - Threat detections
        - Battery warnings
        - System status
    - Mission status tracking:
        - Current position
        - Points covered
        - Battery level
        - Mission duration
```

6. Safety Features:
```
    - Battery monitoring
    - Emergency return
    - Automatic threat logging
    - Error handling
    - Connection monitoring
```

7. User Interface:
```
    - Real-time video displays
    - Patrol controls:
    * Height setting
    * Square size input
    * Start/Stop controls
    - Status indicators
    - Threat alerts
    - Mission timer
    - Keyboard shortcuts
```

8. Data Management:
```
- Automatic threat logging:
  * Date-organized folders
  * Threat images
  * Detailed JSON data
- Mission history
- Status logging
```


From our implementation, here are the patrol controls on the dashboard:

```
9. Configuration Controls:
   ├── Height Control:
   │   ├── Input field: 2-30 meters
   │   ├── Default: 10 meters
   │   └── "Set" button to apply height
   │
   └── Square Size Control:
       ├── Input field: Length in meters
       ├── Used to calculate square perimeter
       └── "Set" button to apply size

10. Patrol Action Buttons:
   ├── "Start Square Patrol":
   │   └── Starts systematic patrol of square perimeter
   │
   ├── "Random Patrol":
   │   ├── If battery > 75%: Generates 3 random points
   │   └── If battery < 75%: Generates 1 random point
   │
   └── "Stop Patrol":
       └── Stops current patrol and returns home
```

11. How these work:

    1.  Height Setting:
    ```python
    # User enters height (e.g., 15 meters)
        - Must be between 2-30 meters
        - Drone will maintain this height during entire patrol
        - Changes take effect immediately
    ```

    2. Square Size:
    ```python
    # User enters single length (e.g., 10 meters)
        - System automatically calculates 4 corner points:
        - Bottom Right (10, 0)  # Starting point
        - Top Right    (10, 10)
        - Top Left     (0, 10)
        - Bottom Left  (0, 0)

    # Square Details:
    - Length of each side: 10 meters
    - Total perimeter: 40 meters (4 sides × 10m)
    - Area covered: 100 square meters (10m × 10m)

        Patrol Points (when viewed from above):
            (0,10)  --------- (10,10)
            |                  |
            |       10m       |
            |    ←——————→     |
            |                 |
            |                 |
            (0,0)   --------- (10,0) start point
    ```
    

    3. Button Functions:
    ```python
    "Start Square Patrol":
        - Drone moves systematically through square corners
        - At each point:
            * Performs 360° scan
            * Checks for threats
            * Proceeds to next point

    "Random Patrol":
        - Battery check determines number of points
        - Generates random coordinates within square
        - Visits points, scans, returns home

    "Stop Patrol":
        - Immediately stops current patrol
        - Returns drone to home position
        - Resets patrol status
    ```

