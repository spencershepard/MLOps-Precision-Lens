"""Kubernetes utility functions for Prefect flows"""
import re


def sanitize_k8s_name(name: str, max_length=63):
    """
    Sanitize a string to be a valid Kubernetes resource name.
    
    Kubernetes names must:
    - Contain only lowercase alphanumeric characters, '-', or '.'
    - Start and end with an alphanumeric character
    - Be at most 63 characters long
    
    Args:
        name: The string to sanitize
        max_length: Maximum length for the name (default: 63)
    
    Returns:
        A sanitized string suitable for use as a Kubernetes resource name
    """
    name = name.lower()
    # Replace invalid characters with '-'
    name = re.sub(r'[^a-z0-9\-\.]', '-', name)
    # Ensure starts/ends with alphanumeric
    name = re.sub(r'^[^a-z0-9]+', '', name)
    name = re.sub(r'[^a-z0-9]+$', '', name)
    # Truncate to max_length
    name = name[:max_length]
    # Ensure ends with alphanumeric after truncation
    name = re.sub(r'[^a-z0-9]+$', '', name)
    return name
