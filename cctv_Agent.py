import cv2
import time
import json
import requests
from ultralytics import YOLO

# --- Configuration ---
# Set your CCTV stream URL (or use 0 for your local webcam)
STREAM_URL = "your_cctv_stream_url_or_0_for_webcam"

# Initialize the YOLO model (make sure 'yolov8n.pt' is available)
yolo_model = YOLO('yolov8n.pt')

# Ollama API configuration:
# This assumes your Ollama API is running locally on port 11434.
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama2"  # Replace with your specific model name if needed

def analyze_detections(detections):
    """
    Create a summary string from YOLO detections.
    """
    detected_objects = set()
    for det in detections:
        cls_id = int(det.cls)
        cls_name = yolo_model.names.get(cls_id, "unknown")
        detected_objects.add(cls_name)
    summary = "Detected: " + ", ".join(detected_objects)
    return summary

def call_ollama(prompt):
    """
    Call the locally running Ollama API with the prompt.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "parameters": {
            "max_tokens": 150,
            "temperature": 0.7
        }
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        # Assuming the response contains a "completion" field with the generated text.
        return result.get("completion", "")
    except Exception as e:
        print("Ollama API call failed:", e)
        return ""

def main():
    # Open the video stream (RTSP or local webcam)
    cap = cv2.VideoCapture(STREAM_URL if STREAM_URL != "0" else 0)
    if not cap.isOpened():
        print("Error: Unable to open video stream.")
        return

    detection_accumulator = []
    start_interval = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Warning: Failed to retrieve frame.")
            break

        # Resize frame for faster processing
        frame_resized = cv2.resize(frame, (640, 480))

        # Run YOLO object detection
        results = yolo_model(frame_resized)

        for result in results:
            detections = result.boxes
            if detections is not None and len(detections) > 0:
                summary = analyze_detections(detections)
                detection_accumulator.append(summary)
                # Display the annotated frame with detections
                annotated_frame = result.plot()
                cv2.imshow("CCTV Monitor", annotated_frame)
            else:
                cv2.imshow("CCTV Monitor", frame_resized)

        # Every 10 seconds, combine detections and ask the local LLM via Ollama
        if time.time() - start_interval > 10:
            if detection_accumulator:
                combined_summary = " ".join(detection_accumulator)
                prompt = (
                    f"Observations from a CCTV feed: {combined_summary}. "
                    "Is there any unusual or concerning activity happening? Answer yes or no with a brief explanation."
                )
                response_text = call_ollama(prompt)
                print("Ollama API response:", response_text)
                # Reset the accumulator for the next interval.
                detection_accumulator = []
            start_interval = time.time()

        # Exit loop when 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
