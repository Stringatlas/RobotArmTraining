"""Local zero-shot object detection using Grounding DINO.

Loads the model once at startup and runs inference directly on the
backend machine (Apple Silicon M4). No remote YOLO server needed.

Detection output is normalized to the same format as the remote
server: {name, conf, x1, y1, x2, y2, cx, cy}
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "IDEA-Research/grounding-dino-base"
DEFAULT_TEXT_THRESHOLD = 0.1

class GroundingDinoDetector:
    """Singleton-style detector that loads the model once and caches it."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        text_threshold: float = DEFAULT_TEXT_THRESHOLD,
    ):
        self.model_name = model_name
        self.text_threshold = text_threshold
        self._processor: Any = None
        self._model: Any = None
        self._device: str = "cpu"

    def load(self) -> None:
        """Load the model and processor. Call once at startup."""
        if self._model is not None:
            return

        # Resolve device
        if torch.cuda.is_available():
            self._device = "cuda"
        elif torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"
        logger.info("Grounding DINO using device: %s", self._device)

        self._processor = AutoProcessor.from_pretrained(self.model_name)
        load_kwargs: dict[str, Any] = {}
        if self._device.startswith("cuda"):
            load_kwargs["torch_dtype"] = torch.float16
        self._model = AutoModelForZeroShotObjectDetection.from_pretrained(
            self.model_name, **load_kwargs
        )
        self._model = self._model.to(self._device)
        self._model.eval()
        logger.info(
            "Loaded Grounding DINO model %s on %s", self.model_name, self._device
        )

    def detect(
        self,
        image_bgr: np.ndarray,
        prompt: str = "object",
    ) -> list[dict[str, Any]]:
        """Run detection on a BGR image (OpenCV format).

        Args:
            image_bgr: BGR image as numpy array.
            prompt: Text prompt for zero-shot detection, e.g. "bottle" or "rubber duck".

        Returns:
            List of detection dicts with keys:
              name, conf, x1, y1, x2, y2, cx, cy
        """
        if self._model is None:
            raise RuntimeError("Detector not loaded. Call load() first.")

        # Convert BGR → RGB → PIL
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)

        inputs = self._processor(
            images=pil_image, text=prompt, return_tensors="pt"
        )

        # Move inputs to device, matching model dtype for float tensors
        try:
            model_dtype = next(self._model.parameters()).dtype
        except StopIteration:
            model_dtype = torch.float32

        moved: dict[str, torch.Tensor] = {}
        for key, value in inputs.items():
            if hasattr(value, "is_floating_point") and value.is_floating_point():
                moved[key] = value.to(device=self._device, dtype=model_dtype)
            else:
                moved[key] = value.to(device=self._device)
        inputs = moved

        with torch.no_grad():
            if model_dtype == torch.float16 and self._device.startswith("cuda"):
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    outputs = self._model(**inputs)
            else:
                outputs = self._model(**inputs)

        results = self._processor.post_process_grounded_object_detection(
            outputs,
            inputs["input_ids"],
            text_threshold=self.text_threshold,
            target_sizes=[pil_image.size[::-1]],
        )

        if not results:
            return []

        detections: list[dict[str, Any]] = []
        for box, score, label in zip(
            results[0]["boxes"], results[0]["scores"], results[0]["labels"]
        ):
            x1 = int(round(float(box[0])))
            y1 = int(round(float(box[1])))
            x2 = int(round(float(box[2])))
            y2 = int(round(float(box[3])))
            detections.append({
                "name": str(label) if label is not None else prompt,
                "conf": float(score),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "cx": int((x1 + x2) / 2),
                "cy": int((y1 + y2) / 2),
            })

        return detections


# Module-level singleton — import and call .load() at startup, then .detect()
detector = GroundingDinoDetector()