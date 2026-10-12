import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def extract_description(record: Dict[str, Any]) -> str:
    """
    Extract 'Nội dung diễn giải' (description) from an invoice record.
    Checks 'description_summary' first, then falls back to concatenating line items.
    
    Args:
        record: The invoice record dictionary.
        
    Returns:
        The extracted description string, cleaned and stripped. Returns empty string if nothing found.
    """
    description = record.get('description_summary', '')
    
    if not description and 'line_items' in record and isinstance(record['line_items'], list):
        description = merge_line_item_descriptions(record['line_items'])
        
    if not description:
        return ''
        
    # Clean up
    description = str(description).strip()
    if description.upper() == 'N/A' or not description:
        return ''
        
    return description

def merge_line_item_descriptions(line_items: List[Dict[str, Any]]) -> str:
    """
    Merge descriptions from a list of line item dictionaries.
    
    Args:
        line_items: List of line items.
        
    Returns:
        A concatenated string of descriptions separated by '; '.
    """
    valid_descriptions = []
    
    for item in line_items:
        if not isinstance(item, dict):
            continue
            
        desc = item.get('description')
        if desc and isinstance(desc, str):
            clean_desc = desc.strip()
            if clean_desc and clean_desc.upper() != 'N/A':
                valid_descriptions.append(clean_desc)
                
    return '; '.join(valid_descriptions)

def truncate_description(text: str, max_length: int = 255) -> str:
    """
    Truncate a description string to a maximum length without splitting words.
    Appends '...' if truncated.
    
    Args:
        text: The text to truncate.
        max_length: Maximum allowed length.
        
    Returns:
        The truncated string.
    """
    if not text or len(text) <= max_length:
        return text
        
    # Subtract length of '...' to ensure final string length <= max_length
    trunc_len = max_length - 3
    if trunc_len <= 0:
        return '...'
        
    truncated_text = text[:trunc_len]
    
    # Avoid truncating in the middle of a word if possible
    last_space_index = truncated_text.rfind(' ')
    if last_space_index > 0:
        truncated_text = truncated_text[:last_space_index]
        
    return truncated_text + '...'
