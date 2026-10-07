# create_user.py
import hashlib
import mysql.connector
from config import DB_CONFIG  # Import database configuration


def hash_password(password: str) -> str:
    """Hashes a password using SHA-256 (same as main.py)."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user_in_db(username, password, email):
    """Connects to the DB and creates a new user."""
    try:
        # Connect to the database using config from config.py
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        hashed_pw = hash_password(password)

        # SQL query to insert the new user
        # Note: user_id and created_at will be set automatically
        insert_query = """
        INSERT INTO users (username, password_hash, email)
        VALUES (%s, %s, %s)
        """

        # Execute the query
        cursor.execute(insert_query, (username, hashed_pw, email))

        # Commit the transaction
        connection.commit()

        print(f"✅ User '{username}' created successfully!")

    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        # Close the connection
        if connection.is_connected():
            cursor.close()
            connection.close()
            print(" MySQL connection closed.")


if __name__ == "__main__":
    # --- Replace these values with your desired credentials ---
    USERNAME = input("Enter desired username: ")
    PASSWORD = input("Enter desired password: ")
    EMAIL = input("Enter email (optional, press Enter to skip): ") or None
    # -----------------------------------------------------------

    if not USERNAME or not PASSWORD:
        print("❌ Username and password cannot be empty.")
    else:
        create_user_in_db(USERNAME, PASSWORD, EMAIL)
