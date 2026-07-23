"""
Natural language command parser for pick-and-place commands.

Supports patterns like:
  "pick up coke can and put at point 8"
  "grab the bottle and place it on the table"
  "take the cup and drop it at zone 3"
"""

import re


_PICK_PATTERNS = [
    r"(?:pick\s+up|grab|take)\s+(?:the\s+)?(.+?)\s+(?:and\s+)?(?:put|place|drop|set)\s+(?:it\s+)?(?:at|on|in|to)?\s*(.+)",
    r"(?:pick|get)\s+(?:the\s+)?(.+?)\s+(?:and\s+)?(?:put|place|drop)\s+(?:it\s+)?(?:at|on|in)?\s*(.+)",
]


def parse_pick_place(text):
    """Parse a pick-and-place command.

    Returns {"object": str, "location": str} or None if no match.
    """
    t = text.strip().lower()
    for pattern in _PICK_PATTERNS:
        m = re.search(pattern, t)
        if m:
            return {
                "object": m.group(1).strip().rstrip(".,"),
                "location": m.group(2).strip().rstrip(".,"),
            }
    return None


def find_best_detection(label, detections):
    """Return the detection best matching label, or None.

    Priority: exact name match > label words in name > name words in label > word overlap.
    Ties broken by confidence.
    """
    if not detections:
        return None

    label = label.lower().strip()
    label_words = set(label.split())

    def score(d):
        name = d["name"].lower()
        name_words = set(name.split())
        if name == label:
            return (4, d["conf"])
        if label in name or name in label:
            return (3, d["conf"])
        overlap = len(label_words & name_words)
        if overlap:
            return (overlap, d["conf"])
        return (0, 0.0)

    scored = [(score(d), d) for d in detections]
    scored = [x for x in scored if x[0][0] > 0]
    if not scored:
        return None
    return max(scored, key=lambda x: x[0])[1]
