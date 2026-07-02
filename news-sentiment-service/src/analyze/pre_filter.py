from typing import Dict


def pre_filter(item: Dict[str, str]) -> bool:
    """Return True for valid items after basic noise filtering."""
    text = item.get("text", "").lower()
    if not text or "buy now" in text or "advertisement" in text:
        return False
    return True
