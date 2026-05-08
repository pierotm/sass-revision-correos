import os
from cryptography.fernet import Fernet
from typing import Optional

class SecurityManager:
    def __init__(self, key: Optional[str] = None):
        """
        Initialize with a Fernet key. 
        If no key is provided, it looks for ENCRYPTION_KEY environment variable.
        """
        self.key = key or os.getenv("ENCRYPTION_KEY")
        if not self.key:
            raise ValueError("No encryption key provided. Set ENCRYPTION_KEY env var.")
        
        self.fernet = Fernet(self.key.encode() if isinstance(self.key, str) else self.key)

    def encrypt(self, data: str) -> str:
        """Encrypts a string and returns a string."""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypts a token string and returns the original string."""
        return self.fernet.decrypt(token.encode() if isinstance(token, str) else token).decode()

# Example usage:
# manager = SecurityManager()
# encrypted = manager.encrypt("my_secret_password")
# decrypted = manager.decrypt(encrypted)
