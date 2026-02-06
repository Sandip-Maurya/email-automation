"""Filter config: allowed sender emails (load/save from JSON)."""

import json
import os
from pathlib import Path

from src.config import PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("email_automation.webhook.filter_config")

# Email validation via email-validator
try:
    from email_validator import validate_email, EmailNotValidError
    _HAS_EMAIL_VALIDATOR = True
except ImportError:
    _HAS_EMAIL_VALIDATOR = False


def get_filter_config_path() -> Path:
    """Path to filter config file (JSON). Override via FILTER_CONFIG_PATH env."""
    raw = os.getenv("FILTER_CONFIG_PATH", "").strip()
    if raw:
        return Path(raw)
    return PROJECT_ROOT / "config" / "filter.json"


def is_valid_email(addr: str) -> bool:
    """Return True if the address is a valid email format."""
    if not addr or not isinstance(addr, str):
        return False
    s = addr.strip()
    if not s:
        return False
    if _HAS_EMAIL_VALIDATOR:
        try:
            validate_email(s)
            return True
        except EmailNotValidError:
            return False
    # Fallback: minimal regex (local@domain with at least one @)
    if s.count("@") != 1:
        return False
    local, domain = s.split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    return True


def _normalize_email(addr: str) -> str:
    return (addr or "").strip().lower()


def _parse_config(path: Path) -> list[str]:
    """Read JSON config file and return raw list from allowed_senders key. Returns [] on missing/invalid."""
    if not path.exists():
        logger.debug("filter_config.file_missing", path=str(path))
        return []
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception as e:
        logger.warning("filter_config.read_error", path=str(path), error=str(e))
        return []
    if not isinstance(data, dict):
        return []
    raw = data.get("allowed_senders")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if x is not None]


def load_allowed_senders() -> list[str]:
    """
    Load allowed_senders from config file. Validates each email; invalid entries are skipped with a log.
    Returns normalized (strip, lower-case) list of valid emails only.
    """
    path = get_filter_config_path()
    raw_list = _parse_config(path)
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_list:
        normalized = _normalize_email(item)
        if not normalized:
            continue
        if not is_valid_email(normalized):
            logger.warning("filter_config.invalid_email_skipped", email=item, path=str(path))
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def save_allowed_senders(senders: list[str]) -> None:
    """
    Persist allowed_senders to the JSON config file. Validates each address; raises ValueError if any invalid.
    Creates parent directory and file if needed.
    """
    path = get_filter_config_path()
    normalized_list: list[str] = []
    for addr in senders:
        n = _normalize_email(addr)
        if not n:
            continue
        if not is_valid_email(n):
            raise ValueError(f"Invalid email format: {addr!r}")
        normalized_list.append(n)
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for x in normalized_list:
        if x not in seen:
            seen.add(x)
            unique.append(x)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"allowed_senders": unique}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("filter_config.saved", path=str(path), count=len(unique))
