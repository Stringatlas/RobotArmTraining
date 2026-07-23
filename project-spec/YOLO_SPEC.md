# YOLO Model Spec

## Model
- Default model: YOLO11 nano (`yolo11n.pt`).
- Intended for lightweight, real-time object detection on RGB frames.

## Inference Strategy
- Primary mode: remote inference via an HTTP detection service.
- Fallback mode: local inference if remote detection is unavailable or times out.
- Detection output is normalized into a common structure: label, confidence, bounding box, and center pixel.

## Core Configuration
- Confidence threshold: `0.35` (for local inference).
- Inference refresh interval: `0.75s`.
- Local inference input size: `320 x 240`.
- Camera stream size: `640 x 480` at `30 FPS`.
- Remote detection poll interval: `0.05s`.
- Remote detection timeout: `1.0s`.

## Runtime Behavior
- Optional class-name filter selects the highest-confidence matching detection.
- The selected target is used to derive 3D point estimates from depth and camera calibration.
- If no valid detection is available, the pipeline returns an empty detection set.
