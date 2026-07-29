"""YOLO object detection using OpenCV DNN, mapped onto the shared threat taxonomy.

This completely replaces the heavy `ultralytics` PyTorch dependency with a robust,
lightweight OpenCV ONNX parser to eliminate DLL loading issues and thread blocks
that lead to SSE disconnections.
"""
import logging
import os
import cv2
import numpy as np
from datetime import datetime, timezone

from config import config
from services.taxonomy import map_detection_class, is_ignored_class

logger = logging.getLogger(__name__)

_net = None

COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 
    'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite', 
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle', 
    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange', 
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant', 
    'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone', 
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 
    'teddy bear', 'hair drier', 'toothbrush'
]


class VisionUnavailableError(RuntimeError):
    """The detection model could not be loaded."""


def _get_model():
    global _net
    if _net is not None:
        return _net
    try:
        _net = cv2.dnn.readNetFromONNX(config.YOLO_WEIGHTS_PATH)
        logger.info("YOLO ONNX weights loaded from %s", config.YOLO_WEIGHTS_PATH)
        return _net
    except Exception as exc:
        logger.exception("Could not load YOLO ONNX weights.")
        raise VisionUnavailableError(
            "Vision engine unavailable: YOLO ONNX weights failed to load."
        ) from exc


def is_ready() -> bool:
    try:
        _get_model()
        return True
    except VisionUnavailableError:
        return False


def detect_objects(image_path: str) -> dict:
    """Run detection and return a structured, taxonomy-aware result.

    Returns a dict with:
      detections  - list of mapped detections (threat_class is never guessed)
      unmapped    - COCO classes with no military analogue, reported not hidden
      model       - which weights produced this
    """
    net = _get_model()
    threshold = config.YOLO_CONFIDENCE_THRESHOLD

    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"OpenCV could not read image at {image_path}")
        original_h, original_w = image.shape[:2]
        
        # YOLOv8 expects 640x640 images
        blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640), swapRB=True, crop=False)
        net.setInput(blob)
        preds = net.forward()
        
        # Parse ONNX output [1, 84, 8400] -> [8400, 84]
        preds = preds[0].T
        boxes = preds[:, :4]
        scores = preds[:, 4:]
        
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        
        # Filter by threshold
        mask = confidences > threshold
        boxes = boxes[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]
        
        # Convert from [x_center, y_center, w, h] normalized?
        # YOLOv8 ONNX returns absolute coordinates in 640x640 space
        x_factor = original_w / 640.0
        y_factor = original_h / 640.0
        
        final_boxes = []
        for i in range(len(boxes)):
            xc, yc, w, h = boxes[i]
            # scale back to original image
            left = int((xc - w/2) * x_factor)
            top = int((yc - h/2) * y_factor)
            width = int(w * x_factor)
            height = int(h * y_factor)
            final_boxes.append([left, top, width, height])
            
        indices = cv2.dnn.NMSBoxes(final_boxes, confidences.tolist(), threshold, 0.4)
        
    except Exception as exc:
        logger.exception("YOLO inference failed for %s", image_path)
        raise VisionUnavailableError("Detection failed for the supplied image.") from exc

    detected_at = datetime.now(timezone.utc)
    detections = []
    unmapped = []

    if len(indices) > 0:
        for i in indices.flatten():
            confidence = float(confidences[i])
            class_id = class_ids[i]
            coco_name = COCO_CLASSES[class_id]
            
            if is_ignored_class(coco_name):
                continue
                
            threat_class, mapped = map_detection_class(coco_name)
            
            left, top, width, height = final_boxes[i]
            # YOLO expects x1, y1, x2, y2 format for output mapping
            x1 = max(0, left)
            y1 = max(0, top)
            x2 = min(original_w, left + width)
            y2 = min(original_h, top + height)

            if not mapped:
                unmapped.append({
                    "source_class": coco_name,
                    "confidence": round(confidence * 100, 2),
                })
                continue

            detections.append({
                "object": threat_class,
                "source_class": coco_name,
                "is_proxy_class": True,
                "confidence": round(confidence * 100, 2),
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "detected_at": detected_at,
            })

    detections.sort(key=lambda d: d["confidence"], reverse=True)

    return {
        "detections": detections,
        "unmapped": unmapped,
        "model": "yolov8n ONNX (COCO proxy classes)",
    }
