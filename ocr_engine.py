# ocr_engine.py
import cv2
import numpy as np
from PIL import Image
import logging
from ultralytics import YOLO
import easyocr  # Or import paddleocr or pytesseract based on config
from config import MODEL_PATH, OCR_ENGINE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(self):
        self.model = None
        self.ocr_reader = None
        self.load_models()

    def load_models(self):
        """Loads the YOLOv8 model and the OCR reader."""
        try:
            logger.info(f"Loading YOLOv8 model from {MODEL_PATH}")
            self.model = YOLO(MODEL_PATH)  # Load the trained model
            logger.info("YOLOv8 model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            self.model = None

        try:
            logger.info(f"Initializing OCR engine: {OCR_ENGINE}")
            if OCR_ENGINE == 'easyocr':
                # Initialize EasyOCR reader (consider specifying languages)
                # Add more languages if needed
                self.ocr_reader = easyocr.Reader(['en'])
            # elif OCR_ENGINE == 'paddleocr':
            #     # Initialize PaddleOCR
            #     from paddleocr import PaddleOCR
            #     self.ocr_reader = PaddleOCR(use_angle_cls=True, lang='en')
            # elif OCR_ENGINE == 'tesseract':
            #     # Tesseract is usually called via pytesseract, no initialization needed here
            #     import pytesseract
            #     self.ocr_reader = pytesseract
            else:
                logger.error(
                    f"Unsupported OCR engine specified in config: {OCR_ENGINE}")
                self.ocr_reader = None
            if self.ocr_reader:
                logger.info(
                    f"OCR engine {OCR_ENGINE} initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize OCR engine {OCR_ENGINE}: {e}")
            self.ocr_reader = None

    def run_yolo_detection(self, image_path):
        """
        Runs YOLOv8 detection on an image.
        Args:
            image_path (str): Path to the image file.
        Returns:
            list: A list of dictionaries, each containing 'x', 'y', 'width', 'height' for a detection.
        """
        if not self.model:
            logger.error("YOLOv8 model is not loaded.")
            return []

        try:
            # Run detection
            results = self.model(image_path)
            detections = []
            # Process results (assuming one image)
            for result in results:
                boxes = result.boxes  # Boxes object for bbox outputs
                if boxes is not None:
                    for box in boxes:  # Iterate through detected boxes
                        # Get box coordinates (xyxy format)
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = xyxy
                        width = x2 - x1
                        height = y2 - y1
                        detections.append({
                            'x': int(x1),
                            'y': int(y1),
                            'width': int(width),
                            'height': int(height)
                        })
            logger.info(f"YOLOv8 detected {len(detections)} regions.")
            return detections
        except Exception as e:
            logger.error(f"Error during YOLOv8 detection: {e}")
            return []

    def run_ocr_on_crop(self, image_np):
        """
        Runs OCR on a given image crop (NumPy array).
        Args:
            image_np (np.ndarray): The image crop as a NumPy array (BGR or RGB).
        Returns:
            tuple: (recognized_text, confidence) or ("", 0.0) on failure.
        """
        if self.ocr_reader is None:
            logger.error("OCR reader is not initialized.")
            return "", 0.0

        try:
            if OCR_ENGINE == 'easyocr':
                # EasyOCR expects RGB or BGR numpy array
                results = self.ocr_reader.readtext(image_np)
                if results:
                    # EasyOCR returns list of (bbox, text, confidence)
                    # Combine text from all detections (YOLO should give tight crops)
                    texts = [res[1] for res in results]
                    confidences = [res[2] for res in results]
                    combined_text = " ".join(texts)
                    avg_confidence = np.mean(
                        confidences) if confidences else 0.0
                    return combined_text.strip(), float(avg_confidence)
                else:
                    return "", 0.0

            # elif OCR_ENGINE == 'paddleocr':
            #     result = self.ocr_reader.ocr(image_np, cls=True)
            #     # Process PaddleOCR result...
            #     # PaddleOCR result structure is more complex...
            #     # Simplified example:
            #     if result and result[0]:
            #         texts = [line[1][0] for line in result[0]]
            #         confidences = [line[1][1] for line in result[0]]
            #         combined_text = " ".join(texts)
            #         avg_confidence = np.mean(confidences) if confidences else 0.0
            #         return combined_text.strip(), float(avg_confidence)
            #     else:
            #         return "", 0.0

            # elif OCR_ENGINE == 'tesseract':
            #     # Using pytesseract
            #     import pytesseract
            #     # Convert BGR (if from OpenCV) to RGB if needed
            #     # image_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            #     # data = pytesseract.image_to_data(image_rgb, output_type=pytesseract.Output.DICT)
            #     # Extract text and confidence...
            #     text = pytesseract.image_to_string(image_np)
            #     # Confidence is trickier with basic pytesseract, often requires --psm 1 or parsing data
            #     # Returning a default confidence for simplicity
            #     return text.strip(), 0.8 # Placeholder confidence

        except Exception as e:
            logger.error(f"Error during OCR processing with {OCR_ENGINE}: {e}")
            return "", 0.0

    def process_auto_ocr(self, image_path):
        """
        Orchestrates the full Auto OCR process: Detect -> Crop -> OCR.
        Args:
            image_path (str): Path to the full image (PDF page converted to image).
        Returns:
            list: A list of dictionaries containing OCR results for each detection.
        """
        logger.info(f"Starting Auto OCR process on {image_path}")
        results = []
        detections = self.run_yolo_detection(image_path)

        if not detections:
            logger.info("No detections found by YOLOv8.")
            return results  # Return empty list

        # Load the full image for cropping
        try:
            full_image = cv2.imread(image_path)
            if full_image is None:
                logger.error(
                    f"Could not load image {image_path} for cropping.")
                return results
        except Exception as e:
            logger.error(f"Error loading image {image_path} for cropping: {e}")
            return results

        for i, det in enumerate(detections):
            x, y, w, h = det['x'], det['y'], det['width'], det['height']
            # Ensure coordinates are within image bounds
            x = max(0, x)
            y = max(0, y)
            w = min(w, full_image.shape[1] - x)
            h = min(h, full_image.shape[0] - y)

            if w > 0 and h > 0:
                crop_img = full_image[y:y+h, x:x+w]
                text, confidence = self.run_ocr_on_crop(crop_img)
                results.append({
                    'bounding_box': det,
                    'recognized_text': text,
                    'confidence': confidence,
                    'mode': 'auto'
                })
                logger.debug(
                    f"Auto OCR Result {i+1}: Text='{text}', Conf={confidence:.2f}")
            else:
                logger.warning(
                    f"Invalid crop dimensions for detection {i+1}: {det}")

        logger.info(
            f"Auto OCR process completed. Found {len(results)} results.")
        return results

    def process_manual_ocr(self, image_path, manual_coords_list):
        """
        Orchestrates the Manual OCR process: Crop -> OCR.
        Args:
            image_path (str): Path to the full image.
            manual_coords_list (list): List of dicts with 'x', 'y', 'width', 'height'.
        Returns:
            list: A list of dictionaries containing OCR results for each manual box.
        """
        logger.info(
            f"Starting Manual OCR process on {image_path} with {len(manual_coords_list)} regions.")
        results = []

        # Load the full image for cropping
        try:
            full_image = cv2.imread(image_path)
            if full_image is None:
                logger.error(
                    f"Could not load image {image_path} for cropping.")
                return results
        except Exception as e:
            logger.error(f"Error loading image {image_path} for cropping: {e}")
            return results

        for i, coords in enumerate(manual_coords_list):
            x, y, w, h = coords['x'], coords['y'], coords['width'], coords['height']
            # Ensure coordinates are within image bounds
            x = max(0, x)
            y = max(0, y)
            w = min(w, full_image.shape[1] - x)
            h = min(h, full_image.shape[0] - y)

            if w > 0 and h > 0:
                crop_img = full_image[y:y+h, x:x+w]
                text, confidence = self.run_ocr_on_crop(crop_img)
                results.append({
                    'bounding_box': coords,  # Use the original coordinates provided
                    'recognized_text': text,
                    'confidence': confidence,
                    'mode': 'manual'
                })
                logger.debug(
                    f"Manual OCR Result {i+1}: Text='{text}', Conf={confidence:.2f}")
            else:
                logger.warning(
                    f"Invalid manual crop dimensions {i+1}: {coords}")

        logger.info(
            f"Manual OCR process completed. Found {len(results)} results.")
        return results

# Example usage (if run directly):
# if __name__ == "__main__":
#     engine = OCREngine()
#     # Example: Process an image (replace 'path/to/page_image.png' with a real path)
#     # auto_results = engine.process_auto_ocr('path/to/page_image.png')
#     # print(auto_results)
