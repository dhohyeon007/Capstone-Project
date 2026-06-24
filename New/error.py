"""
Exceptions
"""


class APIKeyExhaustedError(Exception):
    def __init__(self, message="API Key Exhausted."):
        super().__init__(message)