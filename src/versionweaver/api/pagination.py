import base64
from datetime import datetime


def encode_cursor(created_at: datetime, item_id: str) -> str:
    value = f"{created_at.isoformat()}|{item_id}".encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        timestamp, item_id = base64.urlsafe_b64decode(padded).decode().rsplit("|", 1)
        return datetime.fromisoformat(timestamp), item_id
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid pagination cursor") from exc
