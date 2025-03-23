import cv2
import threading
import numpy as np
from ultralytics import YOLO
import tkinter as tk
from tkinter import Label, Button, Frame
from PIL import Image, ImageTk
import webbrowser


# Load YOLO model (Use "waste_model.pt" if trained)
model = YOLO("yolov8n.pt")

# Define waste categories with corresponding bin types
waste_categories = {
    "banana": "organic", "apple": "organic", "leaves": "organic",  # Organic
    "bottle": "plastic", "bag": "plastic", "straw": "plastic",  # Plastic
    "can": "metal", "tin": "metal", "aluminum": "metal",  # Metal
    "glass": "glass", "bottle-glass": "glass",  # Glass
    "paper": "paper", "cardboard": "paper",  # Paper
    "laptop": "ewaste", "cell phone": "ewaste", "battery": "ewaste",  # E-waste
}

# Bin image paths (Closed/Open)
bin_images = {
    "organic": ["organic_closed.png", "organic_open.png"],
    "plastic": ["plastic_closed.png", "plastic_open.png"],
    "metal": ["metal_closed.png", "metal_open.png"],
    "glass": ["glass_closed.png", "glass_open.png"],
    "paper": ["paper_closed.png", "paper_open.png"],
    "ewaste": ["e-waste_closed.png", "e-waste_open.png"]
}

# Initialize global variables
cap = None
running = False

# Create Tkinter window
root = tk.Tk()
root.title("Smart Bin - Waste Detection")
root.attributes('-fullscreen', True)  # Open in full-screen mode
root.configure(bg="black")

# Function to return to home page
def return_to_home():
    global running, cap
    running = False
    if cap:
        cap.release()
    root.destroy()  # Close the detection window
    webbrowser.open("http://127.0.0.1:5000")  # Redirect back to web UI

# Return Button (Top-left corner)
return_button = Button(root, text="\u2B05", font=("Arial", 16, "bold"), command=return_to_home,
                        bg="gray", fg="white", width=3, height=1, relief="flat", cursor="hand2")
return_button.place(x=10, y=10)

# Function to change button color on hover
def on_enter_exit(e):
    exit_button.config(bg="darkred")

def on_leave_exit(e):
    exit_button.config(bg="red")

def on_enter_start(e):
    start_button.config(bg="darkgreen")

def on_leave_start(e):
    start_button.config(bg="green")

def on_enter_stop(e):
    stop_button.config(bg="darkgreen")

def on_leave_stop(e):
    stop_button.config(bg="green")

# Exit Button (Top-right corner with cursor and hover effects)
exit_button = Button(root, text="✖", font=("Arial", 16, "bold"), command=root.destroy,
                     bg="red", fg="white", width=3, height=1, relief="flat", cursor="hand2")
exit_button.place(x=root.winfo_screenwidth() - 50, y=10)
exit_button.bind("<Enter>", on_enter_exit)
exit_button.bind("<Leave>", on_leave_exit)

# Frame for detection area
detection_frame = Frame(root, bg="gray", width=800, height=500, relief="ridge", bd=5)
detection_frame.pack(pady=20)

# Video display label (inside the frame)
video_label = Label(detection_frame, bg="black", width=800, height=500)
video_label.pack()

# Load a placeholder image for the detection area (ensuring it fits properly)
placeholder_img = Image.open("detection_start.jpeg")
placeholder_img = placeholder_img.resize((800, 500), Image.Resampling.LANCZOS)
placeholder_photo = ImageTk.PhotoImage(placeholder_img)
video_label.configure(image=placeholder_photo)

# Detection result label
result_label = Label(root, text="Detected: None", font=("Arial", 16), fg="white", bg="black")
result_label.pack(pady=10)

# Frame for bins
bin_frame = Frame(root, bg="black")
bin_frame.pack(side=tk.BOTTOM, pady=20)

# Load bin images into memory
bin_labels = {}
bin_images_loaded = {}
for category, paths in bin_images.items():
    closed_img = ImageTk.PhotoImage(Image.open(paths[0]).resize((120, 120)))
    open_img = ImageTk.PhotoImage(Image.open(paths[1]).resize((120, 120)))
    bin_images_loaded[category] = [closed_img, open_img]
    
    # Create bin labels inside the frame
    bin_labels[category] = Label(bin_frame, image=closed_img, bg="black")
    bin_labels[category].pack(side=tk.LEFT, padx=15)

def update_bin_image(category):
    """Update the bin image when waste is detected"""
    if category in bin_labels:
        bin_labels[category].config(image=bin_images_loaded[category][1])  # Open bin
        result_label.config(text=f"Put the waste in {category.capitalize()} bin")

        # Close the bin after 10 seconds
        root.after(5000, lambda: bin_labels[category].config(image=bin_images_loaded[category][0]))

def start_detection():
    """Starts waste detection and displays webcam feed."""
    global cap, running
    running = True
    cap = cv2.VideoCapture(0)

    def detect():
        global running
        while running:
            ret, frame = cap.read()
            if not ret:
                break

            # Perform object detection
            results = model(frame)

            # Process detections
            detected_label = "None"
            category = None
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = box.conf[0]
                    cls = int(box.cls[0])  # Class index

                    # Get the detected object name
                    object_name = model.names.get(cls, "Unknown")

                    # Ignore 'person' detections
                    if object_name.lower() == "person":
                        continue

                    # Categorize detected waste
                    if conf > 0.5:
                        detected_label = f"{object_name}: {conf:.2f}"
                        category = waste_categories.get(object_name.lower(), None)

                        # Draw bounding box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{object_name} ({category})", (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Convert frame to display in Tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            video_label.imgtk = imgtk
            video_label.configure(image=imgtk)

            # Open the corresponding bin
            if category:
                update_bin_image(category)

    threading.Thread(target=detect, daemon=True).start()

def stop_detection():
    """Stops the detection, resets the UI, and restores the placeholder image."""
    global cap, running
    running = False
    if cap:
        cap.release()
    
    # Restore placeholder image
    video_label.config(image=placeholder_photo)
    result_label.config(text="Detected: None")
    
    # Reset all bins to closed state
    for category, bin_label in bin_labels.items():
        bin_label.config(image=bin_images_loaded[category][0])

# Buttons to control detection
button_frame = Frame(root, bg="black")
button_frame.pack(pady=10)

start_button = Button(button_frame, text="Start Detection", font=("Arial", 14), command=start_detection, 
                      bg="green", fg="white", width=15, cursor="hand2")
start_button.pack(side=tk.LEFT, padx=10)
start_button.bind("<Enter>", on_enter_start)
start_button.bind("<Leave>", on_leave_start)

stop_button = Button(button_frame, text="Stop Detection", font=("Arial", 14), command=stop_detection, 
                     bg="green", fg="white", width=15, cursor="hand2")
stop_button.pack(side=tk.RIGHT, padx=10)
stop_button.bind("<Enter>", on_enter_stop)
stop_button.bind("<Leave>", on_leave_stop)

# Run Tkinter main loop
root.mainloop()
