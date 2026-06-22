"""
Input Validation Utilities

Helper functions for validating inputs beyond what Pydantic provides.
"""

import re


# UUID v4 regex pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


DEVICE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-:.]{1,255}$")


def is_valid_uuid(value: str) -> bool:
    """
    Check if a string is a valid UUID v4.

    Args:
        value: String to validate.

    Returns:
        True if the string matches UUID v4 format.
    """
    return bool(UUID_PATTERN.match(value))


def is_valid_device_id(value: str) -> bool:
    """
    Validate a device_id string.

    Device IDs must be 1-255 characters and contain only
    alphanumeric characters, underscores, hyphens, colons, or dots.

    Args:
        value: Device ID string to validate.

    Returns:
        True if valid.
    """
    return bool(DEVICE_ID_PATTERN.match(value))


def sanitize_filename(filename: str) -> str:
    """
    Remove potentially dangerous characters from a filename.

    Args:
        filename: Raw filename string.

    Returns:
        Sanitized filename with only safe characters.
    """
    # Remove path separators and null bytes
    sanitized = re.sub(r'[/\\\0]', '', filename)
    # Remove leading dots (hide files), spaces, and dashes
    sanitized = re.sub(r'^[.\s-]+', '', sanitized)
    # Collapse multiple spaces/dashes
    sanitized = re.sub(r'[-\s]+', '-', sanitized)
    return sanitized.strip() or "untitled"
