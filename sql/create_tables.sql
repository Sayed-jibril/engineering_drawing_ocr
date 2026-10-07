-- Use your desired database name, e.g., 'engineering_ocr_db'
-- CREATE DATABASE IF NOT EXISTS engineering_ocr_db;
-- USE engineering_ocr_db;

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- Store hashed passwords
    email VARCHAR(100) UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table: documents
-- Stores metadata and path to the PDF file
CREATE TABLE IF NOT EXISTS documents (
    doc_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL, -- Original filename
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(500) NOT NULL, -- Path to the PDF on the filesystem
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Table: ocr_results
-- Stores results from both Auto and Manual OCR
CREATE TABLE IF NOT EXISTS ocr_results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id INT NOT NULL,
    mode ENUM('auto', 'manual') NOT NULL, -- Indicates OCR source
    bounding_box JSON NOT NULL, -- Stores coordinates: {"x": ..., "y": ..., "width": ..., "height": ...}
    recognized_text TEXT,
    confidence FLOAT, -- Confidence score from OCR (0.0 to 1.0)
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    label VARCHAR(100), -- Optional user-defined label
    processed_image_path VARCHAR(500), -- Optional path to the saved crop
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Optional: Indexes for performance (consider adding based on query patterns)
-- CREATE INDEX idx_documents_user_id ON documents(user_id);
-- CREATE INDEX idx_ocr_results_doc_id ON ocr_results(doc_id);
-- CREATE INDEX idx_ocr_results_mode ON ocr_results(mode);