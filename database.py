# database.py
import mysql.connector
from mysql.connector import Error, errorcode
import logging
from config import DB_CONFIG
import json
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and interactions for the OCR application.
    Handles user authentication, document metadata, and OCR results.
    """

    def __init__(self):
        """Initializes the DatabaseManager with configuration."""
        self.config = DB_CONFIG
        # Test connection on initialization
        try:
            conn = self.get_connection()
            if conn:
                conn.close()
                logger.info(
                    "DatabaseManager initialized and connection test successful.")
            else:
                logger.error(
                    "DatabaseManager initialization failed: Could not establish test connection.")
        except Exception as e:
            logger.error(f"DatabaseManager initialization error: {e}")

    def get_connection(self):
        """
        Establishes and returns a database connection.
        Returns:
            mysql.connector.connection.MySQLConnection or None: The connection object or None on failure.
        """
        try:
            # Using .copy() is safer to avoid modifying the original config dict if needed elsewhere
            connection_config = self.config.copy()
            # Ensure autocommit is handled explicitly if needed, though it's in the config
            connection = mysql.connector.connect(**connection_config)
            if connection.is_connected():
                db_info = connection.get_server_info()
                logger.debug(f"Connected to MySQL Server version {db_info}")
                return connection
        except Error as e:
            if e.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                logger.error("Error: Access denied for user or password.")
            elif e.errno == errorcode.ER_BAD_DB_ERROR:
                logger.error("Error: Database does not exist.")
            else:
                logger.error(f"Error while connecting to MySQL: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to MySQL: {e}")
        return None

    def create_user(self, username: str, password_hash: str, email: Optional[str] = None) -> Optional[int]:
        """
        Creates a new user in the database.
        Args:
            username (str): The unique username.
            password_hash (str): The hashed password.
            email (str, optional): The user's email address.
        Returns:
            int or None: The new user's ID on success, None on failure.
        """
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor()
                # Use parameterized query to prevent SQL injection
                query = "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)"
                cursor.execute(query, (username, password_hash, email))
                connection.commit()
                user_id = cursor.lastrowid
                logger.info(
                    f"User '{username}' created successfully with ID {user_id}.")
                return user_id
            except Error as e:
                logger.error(f"Database error creating user '{username}': {e}")
                connection.rollback()
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error creating user '{username}': {e}")
                connection.rollback()
                return None
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug("Database connection closed after create_user.")
        return None

    def authenticate_user(self, username: str, password_hash: str) -> Optional[int]:
        """
        Authenticates a user by username and hashed password.
        Args:
            username (str): The username.
            password_hash (str): The hashed password provided by the user (should match the stored hash).
        Returns:
            int or None: The user's ID if authentication is successful, None otherwise.
        """
        connection = self.get_connection()
        if connection:
            try:
                # Fetch rows as dictionaries
                cursor = connection.cursor(dictionary=True)
                # Use parameterized query
                query = "SELECT user_id FROM users WHERE username = %s AND password_hash = %s"
                cursor.execute(query, (username, password_hash))
                result = cursor.fetchone()  # fetchone() returns None if no row is found
                if result:
                    user_id = result['user_id']
                    logger.info(
                        f"User '{username}' (ID: {user_id}) authenticated successfully.")
                    return user_id
                else:
                    logger.info(
                        f"Authentication failed for username '{username}'.")
                    return None
            except Error as e:
                logger.error(
                    f"Database error during authentication for '{username}': {e}")
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error during authentication for '{username}': {e}")
                return None
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug(
                    "Database connection closed after authenticate_user.")
        return None

    def save_document(self, user_id: int, filename: str, file_path: str) -> Optional[int]:
        """
        Saves document metadata to the database.
        Args:
            user_id (int): The ID of the user who owns the document.
            filename (str): The original name of the uploaded file.
            file_path (str): The path where the file is stored on the server.
        Returns:
            int or None: The new document's ID on success, None on failure.
        """
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor()
                # Use parameterized query
                query = "INSERT INTO documents (user_id, filename, file_path) VALUES (%s, %s, %s)"
                cursor.execute(query, (user_id, filename, file_path))
                connection.commit()
                doc_id = cursor.lastrowid
                logger.info(
                    f"Document '{filename}' (Path: {file_path}) saved for user ID {user_id} with Doc ID {doc_id}.")
                return doc_id
            except Error as e:
                logger.error(
                    f"Database error saving document '{filename}': {e}")
                connection.rollback()
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error saving document '{filename}': {e}")
                connection.rollback()
                return None
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug("Database connection closed after save_document.")
        return None

    def get_user_documents(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves a list of documents for a specific user, ordered by upload time.
        Args:
            user_id (int): The ID of the user.
        Returns:
            list: A list of dictionaries, each representing a document with keys:
                  'doc_id', 'filename', 'upload_timestamp', 'file_path'.
                  Returns an empty list on failure or if no documents are found.
        """
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                # --- FIX: Include file_path in the SELECT query ---
                query = """
                    SELECT doc_id, filename, upload_timestamp, file_path 
                    FROM documents 
                    WHERE user_id = %s 
                    ORDER BY upload_timestamp DESC
                """
                # --- END FIX ---
                cursor.execute(query, (user_id,))
                # fetchall() returns a list of dicts (because of dictionary=True)
                results = cursor.fetchall()
                logger.info(
                    f"Retrieved {len(results)} documents for user ID {user_id}.")
                return results
            except Error as e:
                logger.error(
                    f"Database error retrieving documents for user ID {user_id}: {e}")
                return []
            except Exception as e:
                logger.error(
                    f"Unexpected error retrieving documents for user ID {user_id}: {e}")
                return []
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug(
                    "Database connection closed after get_user_documents.")
        return []

    def save_ocr_result(self, doc_id: int, mode: str, bounding_box: Dict[str, int],
                        recognized_text: str, confidence: Optional[float] = None,
                        label: Optional[str] = None, processed_image_path: Optional[str] = None) -> Optional[int]:
        """
        Saves an OCR result to the database.
        Args:
            doc_id (int): The ID of the document the result belongs to.
            mode (str): The OCR mode ('auto' or 'manual').
            bounding_box (dict): A dictionary with keys 'x', 'y', 'width', 'height'.
            recognized_text (str): The text recognized by the OCR engine.
            confidence (float, optional): The confidence score from the OCR engine.
            label (str, optional): An optional user-defined label for the result.
            processed_image_path (str, optional): Path to the saved cropped image.
        Returns:
            int or None: The new result's ID on success, None on failure.
        """
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor()
                # Convert bounding box dict to JSON string for storage
                bbox_json = json.dumps(bounding_box)

                query = """
                    INSERT INTO ocr_results 
                    (doc_id, mode, bounding_box, recognized_text, confidence, label, processed_image_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (doc_id, mode, bbox_json,
                               recognized_text, confidence, label, processed_image_path))
                connection.commit()
                result_id = cursor.lastrowid
                logger.info(
                    f"OCR result saved for Doc ID {doc_id} with Result ID {result_id}.")
                return result_id
            except Error as e:
                logger.error(
                    f"Database error saving OCR result for Doc ID {doc_id}: {e}")
                connection.rollback()
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error saving OCR result for Doc ID {doc_id}: {e}")
                connection.rollback()
                return None
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug(
                    "Database connection closed after save_ocr_result.")
        return None

    def get_ocr_results(self, doc_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves OCR results for a specific document.
        Args:
            doc_id (int): The ID of the document.
        Returns:
            list: A list of dictionaries, each representing an OCR result with keys:
                  'result_id', 'mode', 'bounding_box' (dict), 'recognized_text', 'confidence',
                  'timestamp', 'label'. Returns an empty list on failure or if no results.
        """
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                query = """
                    SELECT result_id, mode, bounding_box, recognized_text, confidence, timestamp, label
                    FROM ocr_results
                    WHERE doc_id = %s
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (doc_id,))
                results = cursor.fetchall()
                # Convert bounding_box JSON string back to Python dict
                for result in results:
                    try:
                        # json.loads can raise JSONDecodeError
                        result['bounding_box'] = json.loads(
                            result['bounding_box']) if result['bounding_box'] else None
                    except json.JSONDecodeError as e:
                        logger.error(
                            f"Error decoding bounding_box JSON for result ID {result.get('result_id')}: {e}")
                        # Set to None if JSON is invalid
                        result['bounding_box'] = None

                logger.info(
                    f"Retrieved {len(results)} OCR results for Doc ID {doc_id}.")
                return results
            except Error as e:
                logger.error(
                    f"Database error retrieving OCR results for Doc ID {doc_id}: {e}")
                return []
            except Exception as e:
                logger.error(
                    f"Unexpected error retrieving OCR results for Doc ID {doc_id}: {e}")
                return []
            finally:
                if cursor:
                    cursor.close()
                connection.close()
                logger.debug(
                    "Database connection closed after get_ocr_results.")
        return []

# Example usage (if run directly):
# if __name__ == "__main__":
#     db = DatabaseManager()
#     # Test connection
#     conn = db.get_connection()
#     if conn:
#         conn.close()
#         print("Connection test passed.")
#     else:
#         print("Connection test failed.")
#
#     # Example: Create a user (password should be hashed!)
#     # hashed_pw = "your_hashed_password_here" # Use hash_password function from main.py
#     # user_id = db.create_user("testuser", hashed_pw, "test@example.com")
#     # print(f"Created user ID: {user_id}")
#
#     # Example: Authenticate user
#     # auth_user_id = db.authenticate_user("testuser", hashed_pw)
#     # print(f"Authenticated user ID: {auth_user_id}")
