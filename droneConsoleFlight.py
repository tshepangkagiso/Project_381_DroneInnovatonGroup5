from djitellopy import Tello
import time
 
# Initialize the Tello drone
tello = Tello()
tello.connect()
 
# Parameters in centimeters
side_length = 200  # Side length of the square perimeter in cm
height = 150       # Desired height in cm
 
# Coordinates for each corner relative to the origin (Bottom Right)
corners = {
    "top_left": (-side_length, side_length),
    "top_right": (side_length, side_length),
    "bottom_left": (-side_length, -side_length),
    "bottom_right": (0, 0)  # Origin (BR)
}
def perimeter():
    # Takeoff and reach the desired height
    tello.takeoff()
    
    print("Drone took off")
    time.sleep(0.5)
 
    tello.move_up(150)  # Adjust for initial takeoff height
    print(f"Drone moved up to {height} cm")
    time.sleep(0.5)

    tello.move_forward(side_length)
    print(f"Drone moved forward to {height} cm")
    time.sleep(0.5)

    tello.rotate_clockwise(360)
    print("Drone completed 360-degree scan")
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    print("Drone completed 270-degree scan face tl")
    time.sleep(0.5)

    tello.move_forward(side_length)
    print(f"Drone moved forward to {height} cm")
    time.sleep(0.5)

    tello.rotate_clockwise(360)
    print("Drone completed 360-degree scan")
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    print("Drone completed 270-degree scan face bl")
    time.sleep(0.5)

    tello.move_forward(side_length)
    print(f"Drone moved forward to {height} cm")
    time.sleep(0.5)

    tello.rotate_clockwise(360)
    print("Drone completed 360-degree scan")
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    print("Drone completed 270-degree scan face br origin")
    time.sleep(0.5)

    tello.move_forward(side_length)
    print(f"Drone moved forward to {height} cm")
    time.sleep(0.5)

    tello.rotate_clockwise(360)
    print("Drone completed 360-degree scan")
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    print("Drone completed 270-degree scan face tr")
    time.sleep(0.5)

    # Move down slowly to ensure a controlled landing close to the takeoff position
    tello.move_down(height)
    print("Drone moved down to prepare for landing")
 
    # Land the drone
    tello.land()
    print("Drone landed")
 
def fly_to_TopRight():
    # Takeoff and reach the desired height
    tello.takeoff()
    print("Drone took off")
    time.sleep(1)
 
    tello.move_up(150)  # Adjust for initial takeoff height
    print(f"Drone moved up to {height} cm")
    time.sleep(1)

    tello.move_forward(side_length)
    print(f"Drone moved forward to {height} cm")
    time.sleep(1)

    tello.rotate_clockwise(360)
    print("Drone completed 360-degree scan")
    time.sleep(1)

    tello.move_back(side_length)
    print("Drone move to origin")
    time.sleep(1)

    # Move down slowly to ensure a controlled landing close to the takeoff position
    tello.move_down(height)
    print("Drone moved down to prepare for landing")
 
    # Land the drone
    tello.land()
    print("Drone landed")




def fly_to_TopLeft():
     # Takeoff and reach the desired height
    tello.takeoff()
    print("Drone took off")
    time.sleep(1)

    tello.move_up(150)  # Adjust for initial takeoff height
    print(f"Drone moved up to {height} cm")
    time.sleep(1)

    tello.rotate_clockwise(270)
    time.sleep(0.5)

    tello.move_forward(side_length)
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    time.sleep(0.5)

    tello.move_forward(side_length)
    time.sleep(0.5)

    tello.move_back(side_length)
    time.sleep(0.5)

    tello.rotate_clockwise(90)
    time.sleep(0.5)

    tello.move_forward(side_length)
    time.sleep(0.5)

    tello.rotate_counter_clockwise(90)
    time.sleep(0.5)

    # Move down slowly to ensure a controlled landing close to the takeoff position
    tello.move_down(height)
    print("Drone moved down to prepare for landing")
 
    # Land the drone
    tello.land()
    print("Drone landed")





def fly_to_BottomLeft():
    # Takeoff and reach the desired height
    tello.takeoff()
    print("Drone took off")
    time.sleep(0.5)

    tello.move_up(150)  # Adjust for initial takeoff height
    print(f"Drone moved up to {height} cm")
    time.sleep(0.5)

    tello.rotate_clockwise(270)
    time.sleep(0.5)

    tello.move_forward(side_length)
    time.sleep(0.5)

    tello.rotate_clockwise(180)
    time.sleep(0.5)

    tello.move_forward(side_length)
    time.sleep(0.5)

    tello.rotate_counter_clockwise(90)
    time.sleep(0.5)

    # Move down slowly to ensure a controlled landing close to the takeoff position
    tello.move_down(height)
    print("Drone moved down to prepare for landing")
 
    # Land the drone
    tello.land()
    print("Drone landed")
    
 
# Main loop to select a corner to fly to
def main():
    while True:
        print("\nChoose flight path:")
        print("1 for Bottom Left (BL), 2 for Top Left (TL), 3 for Top Right (TR), or 'q' to quit")
        choice = input("Enter 1, 2, 3, 4, or 'q': ")
 
        if choice == "1":
            fly_to_BottomLeft()
        elif choice == "2":
            fly_to_TopLeft()
        elif choice == "3":
            fly_to_TopRight()
        elif choice == "4":
            perimeter()
        elif choice.lower() == 'q':
            print("Exiting flight control")
            break
        else:
            print("Invalid choice. Please try again.")
 
# Execute the main function
if __name__ == "__main__":
    main()