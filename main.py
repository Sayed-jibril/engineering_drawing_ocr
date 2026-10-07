# main.py
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QStatusBar, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox, QSplitter, QFrame, QToolBar, QMenuBar, QMenu
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QAction, QIcon
from PySide6.QtCore import Qt, QRectF, QPoint, Slot, Signal, QObject, QSize
# For password hashing (use a stronger method like bcrypt in production)
import hashlib
import fitz  # pymupdf for PDF handling
from database import DatabaseManager
from ocr_engine import OCREngine
from config import PDF_STORAGE_DIR, IMAGE_STORAGE_DIR
import logging

# Configure logging
# Change to WARNING/INFO/DEBUG as needed
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Utility Functions ---


def hash_password(password: str) -> str:
    """Hashes a password using SHA-256 (Replace with bcrypt or similar for production!)."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- Custom Graphics View for Drawing, Panning, and Zooming ---


class DrawingGraphicsView(QGraphicsView):
    # Signal emitted when a manual box is drawn (x, y, width, height)
    manual_box_drawn = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        # --- Zoom and Pan Settings ---
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # Default to panning
        self.setTransformationAnchor(
            QGraphicsView.AnchorUnderMouse)  # Zoom centered on mouse
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setFrameShape(QFrame.NoFrame)  # Cleaner look

        # --- Drawing State ---
        self._start_point = QPoint()
        self._current_rect_item = None
        self.drawing_enabled = False  # Flag to enable/disable drawing

        # Set initial cursor
        self.viewport().setCursor(Qt.ArrowCursor)

    def enable_drawing(self):
        """Enable manual drawing mode."""
        self.drawing_enabled = True
        self.setDragMode(QGraphicsView.NoDrag)  # Disable panning while drawing
        self.viewport().setCursor(Qt.CrossCursor)  # Change cursor to crosshair
        logger.info("Manual drawing mode enabled.")

    def disable_drawing(self):
        """Disable manual drawing mode."""
        self.drawing_enabled = False
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # Re-enable panning
        self.viewport().setCursor(Qt.ArrowCursor)  # Reset cursor
        logger.info("Manual drawing mode disabled.")

    # --- Mouse Event Overrides for Drawing ---
    def mousePressEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.LeftButton:
            self._start_point = self.mapToScene(event.pos()).toPoint()
            if self._current_rect_item:
                self.scene().removeItem(self._current_rect_item)
            self._current_rect_item = None
        else:
            # Call parent implementation for panning (ScrollHandDrag) or other interactions
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_enabled and event.buttons() & Qt.LeftButton and self._start_point:
            if not self._current_rect_item:
                self._current_rect_item = QGraphicsRectItem()
                self._current_rect_item.setPen(
                    QPen(QColor("red"), 2, Qt.SolidLine))
                self.scene().addItem(self._current_rect_item)
            current_point = self.mapToScene(event.pos()).toPoint()
            rect = QRectF(self._start_point, current_point).normalized()
            self._current_rect_item.setRect(rect)
        else:
            # Call parent implementation for panning or other interactions
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.LeftButton and self._current_rect_item:
            rect = self._current_rect_item.rect()
            if rect.width() > 5 and rect.height() > 5:  # Minimum size check
                # Emit signal with bounding box coordinates
                box_coords = {
                    'x': int(rect.x()),
                    'y': int(rect.y()),
                    'width': int(rect.width()),
                    'height': int(rect.height())
                }
                self.manual_box_drawn.emit(box_coords)
                logger.debug(f"Manual box drawn: {box_coords}")
            # Keep the rectangle on the scene for visual feedback, or remove it
            # For now, we'll keep it until the next draw or image load
            # self.scene().removeItem(self._current_rect_item) # Optional: remove after emit
            # self._current_rect_item = None # Optional: reset item
            self._start_point = QPoint()  # Reset start point
        else:
            # Call parent implementation for panning or other interactions
            super().mouseReleaseEvent(event)

    # --- Wheel Event Override for Zooming ---
    def wheelEvent(self, event):
        """Handle mouse wheel zooming."""
        if event.angleDelta().y() > 0:
            factor = 1.25  # Zoom in
        else:
            factor = 0.8  # Zoom out

        # Apply zoom transformation
        self.scale(factor, factor)

        # Optional: Limit zoom range
        # current_scale = self.transform().m11() # Get current X scale factor
        # if current_scale < 0.1 or current_scale > 10:
        #     # Reset scale if out of bounds
        #     self.resetTransform()
        #     self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    # --- Optional: Reset View ---
    def reset_view(self):
        """Reset the view to fit the entire scene."""
        if self.scene():
            self.resetTransform()  # Reset any zoom/pan transformations
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
            logger.debug("Canvas view reset.")

# --- Login Dialog ---


class LoginDialog(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Login")
        self.setModal(True)
        self.user_id = None

        layout = QFormLayout(self)

        self.username_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)

        layout.addRow("Username:", self.username_input)
        layout.addRow("Password:", self.password_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Input Error",
                                "Please enter both username and password.")
            return

        hashed_pw = hash_password(password)  # Hash input password
        user_id = self.db_manager.authenticate_user(username, hashed_pw)
        if user_id:
            self.user_id = user_id
            super().accept()  # Close dialog successfully
        else:
            QMessageBox.warning(self, "Login Failed",
                                "Invalid username or password.")

# --- Main Application Window ---


class MainWindow(QMainWindow):
    def __init__(self, user_id: int, db_manager: DatabaseManager, ocr_engine: OCREngine):
        super().__init__()
        self.user_id = user_id
        self.db_manager = db_manager
        self.ocr_engine = ocr_engine
        self.current_doc_id = None
        self.current_page_image_path = None  # Path to the image of the current PDF page
        self.setWindowTitle("Engineering Drawing OCR Tool")
        self.setGeometry(100, 100, 1200, 800)

        # Central Widget and Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Toolbar ---
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))  # Slightly larger icons

        self.action_open_pdf = QAction(
            QIcon.fromTheme("document-open"), "Open PDF", self)
        self.action_open_pdf.triggered.connect(self.open_pdf)
        toolbar.addAction(self.action_open_pdf)

        self.action_auto_ocr = QAction(
            QIcon.fromTheme("system-run"), "Auto OCR", self)
        self.action_auto_ocr.triggered.connect(self.run_auto_ocr)
        # Disabled until a PDF page is loaded
        self.action_auto_ocr.setEnabled(False)
        toolbar.addAction(self.action_auto_ocr)

        self.action_manual_ocr = QAction(QIcon.fromTheme(
            "input-mouse"), "Process Manual OCR", self)
        self.action_manual_ocr.triggered.connect(self.run_manual_ocr)
        # Disabled until manual boxes are drawn
        self.action_manual_ocr.setEnabled(False)
        toolbar.addAction(self.action_manual_ocr)

        # --- Drawing Toggle Button ---
        self.btn_toggle_drawing = QPushButton("Enable Manual Drawing")
        self.btn_toggle_drawing.setCheckable(True)
        self.btn_toggle_drawing.toggled.connect(self.toggle_drawing)
        toolbar.addWidget(self.btn_toggle_drawing)

        # --- Reset View Button ---
        self.action_reset_view = QAction(
            QIcon.fromTheme("view-refresh"), "Reset View", self)
        self.action_reset_view.triggered.connect(self.reset_canvas_view)
        toolbar.addAction(self.action_reset_view)
        # --- End Toolbar Additions ---

        # --- Splitter for Canvas and Table ---
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Panel: Canvas ---
        self.canvas_frame = QFrame()
        canvas_layout = QVBoxLayout(self.canvas_frame)
        self.graphics_view = DrawingGraphicsView()
        self.graphics_view.manual_box_drawn.connect(self.on_manual_box_drawn)
        self.scene = QGraphicsScene(self.graphics_view)
        self.graphics_view.setScene(self.scene)
        canvas_layout.addWidget(self.graphics_view)
        splitter.addWidget(self.canvas_frame)
        # Give more space to canvas
        splitter.setStretchFactor(splitter.count() - 1, 3)

        # --- Right Panel: Results Table ---
        self.table_frame = QFrame()
        table_layout = QVBoxLayout(self.table_frame)
        self.results_table = QTableWidget(0, 6)  # 6 columns
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Mode", "Text", "Confidence", "Coordinates", "Label"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.results_table.setEditTriggers(
            QTableWidget.NoEditTriggers)  # Make read-only
        table_layout.addWidget(self.results_table)
        splitter.addWidget(self.table_frame)
        splitter.setStretchFactor(
            splitter.count() - 1, 2)  # Less space for table

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Store manual boxes drawn by the user
        self.manual_boxes = []

    @Slot()
    def open_pdf(self):
        """Handle opening a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf)")
        if file_path:
            try:
                doc_id = self.load_pdf(file_path)
                if doc_id:
                    self.current_doc_id = doc_id
                    # Load the first page (or let user select)
                    self.load_pdf_page(0)  # Load page 0 by default
                    self.action_auto_ocr.setEnabled(True)
                    self.status_bar.showMessage(
                        f"Loaded PDF: {Path(file_path).name}")
                else:
                    QMessageBox.critical(
                        self, "Error", "Failed to save document to database.")
            except Exception as e:
                logger.error(f"Error opening PDF {file_path}: {e}")
                QMessageBox.critical(self, "Error", f"Could not open PDF: {e}")

    def load_pdf(self, file_path: str) -> int:
        """Save PDF metadata to DB and copy file."""
        filename = Path(file_path).name
        # Define storage path
        dest_path = PDF_STORAGE_DIR / filename
        # Simple copy (consider handling name conflicts)
        try:
            with open(file_path, 'rb') as fsrc, open(dest_path, 'wb') as fdst:
                fdst.write(fsrc.read())
            # Save metadata to DB
            doc_id = self.db_manager.save_document(
                self.user_id, filename, str(dest_path))
            return doc_id
        except Exception as e:
            logger.error(f"Error saving PDF {file_path}: {e}")
            return None

    def load_pdf_page(self, page_num: int):
        """Convert a PDF page to image and display it."""
        if not self.current_doc_id:
            logger.warning("No current document ID set.")
            return

        # Get document path from DB - FIXED: Ensure file_path is fetched
        docs = self.db_manager.get_user_documents(self.user_id)
        doc_path_str = next(
            (doc['file_path'] for doc in docs if doc['doc_id'] == self.current_doc_id), None)
        if not doc_path_str:
            logger.error(
                "Could not find document path in database for doc_id: %s", self.current_doc_id)
            QMessageBox.critical(
                self, "Error", "Document path not found in database.")
            return

        doc_path = Path(doc_path_str)
        if not doc_path.exists():
            logger.error(f"PDF file not found at {doc_path}")
            QMessageBox.critical(
                self, "Error", f"PDF file not found on disk: {doc_path}")
            return

        try:
            # Use pymupdf (fitz) to convert page to image
            pdf_document = fitz.open(doc_path)
            if page_num >= pdf_document.page_count:
                logger.warning(
                    f"Page number {page_num} out of range for document {doc_path.name}.")
                pdf_document.close()
                QMessageBox.warning(
                    self, "Warning", f"Page number {page_num + 1} is out of range.")
                return

            page = pdf_document[page_num]
            mat = fitz.Matrix(2.0, 2.0)  # Zoom in for better OCR
            pix = page.get_pixmap(matrix=mat)
            # Convert pixmap to QImage
            img_data = pix.tobytes("ppm")  # Get PPM format bytes
            qimage = QImage.fromData(img_data, "PPM")
            pdf_document.close()

            if qimage.isNull():
                logger.error("Failed to convert PDF page to QImage.")
                QMessageBox.critical(
                    self, "Error", "Failed to convert PDF page to image.")
                return

            # Save image temporarily
            image_filename = f"temp_page_{self.current_doc_id}_{page_num}.png"
            self.current_page_image_path = IMAGE_STORAGE_DIR / image_filename
            qimage.save(str(self.current_page_image_path), "PNG")

            # Display image on canvas
            self.display_image_on_canvas(str(self.current_page_image_path))
            self.status_bar.showMessage(
                f"Displaying page {page_num + 1} of {doc_path.name}")

        except Exception as e:
            # Log full traceback
            logger.error(
                f"Error loading PDF page {page_num}: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error", f"Could not load PDF page: {e}")

    def display_image_on_canvas(self, image_path: str):
        """Display an image on the QGraphicsView."""
        self.scene.clear()
        self.manual_boxes = []  # Clear manual boxes when a new image is loaded
        self.action_manual_ocr.setEnabled(False)  # Disable manual OCR button
        self.btn_toggle_drawing.setChecked(False)  # Uncheck drawing button
        self.graphics_view.disable_drawing()  # Ensure drawing is off

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logger.error(f"Failed to load pixmap from {image_path}")
            QMessageBox.critical(
                self, "Error", f"Failed to load image for display: {image_path}")
            return

        pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.graphics_view.fitInView(
            self.scene.sceneRect(), Qt.KeepAspectRatio)

    @Slot(dict)
    def on_manual_box_drawn(self, box_coords: dict):
        """Slot to handle a new manual box drawn by the user."""
        self.manual_boxes.append(box_coords)
        # Enable the manual OCR button once at least one box is drawn
        if not self.action_manual_ocr.isEnabled():
            self.action_manual_ocr.setEnabled(True)
        logger.debug(f"Box added to manual list: {box_coords}")

    @Slot()
    def toggle_drawing(self, checked: bool):
        """Toggle manual drawing mode."""
        if checked:
            self.graphics_view.enable_drawing()
            self.btn_toggle_drawing.setText("Disable Manual Drawing")
        else:
            self.graphics_view.disable_drawing()
            self.btn_toggle_drawing.setText("Enable Manual Drawing")

    @Slot()
    def reset_canvas_view(self):
        """Slot to reset the canvas view."""
        self.graphics_view.reset_view()
        self.status_bar.showMessage("Canvas view reset.")

    @Slot()
    def run_auto_ocr(self):
        """Run the Auto OCR process."""
        if not self.current_page_image_path or not self.current_doc_id:
            QMessageBox.warning(self, "Error", "No PDF page loaded.")
            return

        self.status_bar.showMessage("Running Auto OCR...")
        QApplication.processEvents()  # Update UI

        try:
            results = self.ocr_engine.process_auto_ocr(
                str(self.current_page_image_path))
            self.save_and_display_results(results)
            self.status_bar.showMessage("Auto OCR completed.")
        except Exception as e:
            logger.error(f"Error during Auto OCR: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Auto OCR failed: {e}")
            self.status_bar.showMessage("Auto OCR failed.")

    @Slot()
    def run_manual_ocr(self):
        """Run the Manual OCR process."""
        if not self.current_page_image_path or not self.current_doc_id or not self.manual_boxes:
            QMessageBox.warning(
                self, "Error", "No manual boxes drawn or PDF page not loaded.")
            return

        self.status_bar.showMessage("Running Manual OCR...")
        QApplication.processEvents()  # Update UI

        try:
            results = self.ocr_engine.process_manual_ocr(
                str(self.current_page_image_path), self.manual_boxes)
            self.save_and_display_results(results)
            # Clear boxes after processing
            self.manual_boxes.clear()
            self.action_manual_ocr.setEnabled(False)
            self.status_bar.showMessage("Manual OCR completed.")
        except Exception as e:
            logger.error(f"Error during Manual OCR: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Manual OCR failed: {e}")
            self.status_bar.showMessage("Manual OCR failed.")

    def save_and_display_results(self, results: list):
        """Save OCR results to DB and display them in the table."""
        if not results or self.current_doc_id is None:
            logger.info("No results to save or display.")
            return

        saved_count = 0
        for result in results:
            # Save to database
            res_id = self.db_manager.save_ocr_result(
                doc_id=self.current_doc_id,
                mode=result['mode'],
                bounding_box=result['bounding_box'],
                recognized_text=result['recognized_text'],
                confidence=result['confidence']
                # label and processed_image_path are optional
            )
            if res_id:
                saved_count += 1
            # Note: Saving the crop image is optional and not implemented here for brevity.
            # You could save `crop_img` from `ocr_engine.py` to a file and pass the path.

        logger.info(
            f"Saved {saved_count}/{len(results)} OCR results to database.")

        # Refresh the results table
        self.load_results_table()
        self.status_bar.showMessage(
            f"Processed {len(results)} regions ({saved_count} saved).")

    def load_results_table(self):
        """Load OCR results from DB and populate the table."""
        if self.current_doc_id is None:
            self.results_table.setRowCount(0)
            logger.debug("No current document ID, cleared results table.")
            return

        results = self.db_manager.get_ocr_results(self.current_doc_id)
        self.results_table.setRowCount(len(results))

        for row, result in enumerate(results):
            self.results_table.setItem(
                row, 0, QTableWidgetItem(str(result['result_id'])))
            self.results_table.setItem(
                row, 1, QTableWidgetItem(result['mode'].title()))
            self.results_table.setItem(
                row, 2, QTableWidgetItem(result['recognized_text']))
            conf_item = QTableWidgetItem(
                f"{result['confidence']:.2f}" if result['confidence'] is not None else "N/A")
            self.results_table.setItem(row, 3, conf_item)
            bbox = result['bounding_box']
            coord_str = f"({bbox['x']}, {bbox['y']}, {bbox['width']}, {bbox['height']})" if bbox else "N/A"
            self.results_table.setItem(row, 4, QTableWidgetItem(coord_str))
            self.results_table.setItem(row, 5, QTableWidgetItem(
                result.get('label', '')))  # Label column

        self.results_table.resizeColumnsToContents()
        # self.results_table.sortByColumn(0, Qt.AscendingOrder) # Sort by ID - optional
        logger.debug(f"Loaded {len(results)} results into the table.")


# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Initialize core components
    db_manager = DatabaseManager()
    ocr_engine = OCREngine()  # This will load models

    # Show Login Dialog
    login_dialog = LoginDialog(db_manager)
    if login_dialog.exec() == QDialog.Accepted:
        user_id = login_dialog.user_id
        if user_id:
            logger.info(f"User ID {user_id} logged in.")
            # Create and show main window
            main_window = MainWindow(user_id, db_manager, ocr_engine)
            main_window.show()
            sys.exit(app.exec())
        else:
            logger.error("Login failed, exiting.")
            QMessageBox.critical(None, "Login Error",
                                 "Login failed. Exiting application.")
            sys.exit(1)
    else:
        logger.info("Login cancelled, exiting.")
        sys.exit(0)
