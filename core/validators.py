
cat > core/validators.py <<'PYEOF'
"""
core/validators.py — input validation and normalization.
"""

import hashlib
import re
from typing import Optional

import phonenumbers
from email_validator import validate_email, EmailNotValidError


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)


def is_username(s: str) -> bool:
    return bool(USERNAME_RE.match(s.strip()))


def is_domain(s: str) -> bool:
    return bool(DOMAIN_RE.match(s.strip().lower()))


def is_email(s: str) -> bool:
    try:
        validate_email(s, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def normalize_phone(raw: str, default_region: str = "IN") -> Optional[str]:
    """Return E.164 phone number or None."""
    raw = raw.strip()
    try:
        num = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def phone_info(raw: str, default_region: str = "IN") -> Optional[dict]:
    """Return dict with country, carrier, line_type, timezone."""
    e164 = normalize_phone(raw, default_region)
    if not e164:
        return None
    num = phonenumbers.parse(e164, None)
    carrier = phonenumbers.carrier.name_for_number(num, "en") or "unknown"
    region = phonenumbers.region_code_for_number(num) or "unknown"
    line_type_raw = phonenumbers.number_type(num)
    line_map = {
        phonenumbers.PhoneNumberType.MOBILE: "mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE: "landline",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
        phonenumbers.PhoneNumberType.TOLL_FREE: "toll_free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium",
        phonenumbers.PhoneNumberType.VOIP: "voip",
        phonenumbers.PhoneNumberType.SHARED_COST: "shared_cost",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "personal",
        phonenumbers.PhoneNumberType.PAGER: "pager",
        phonenumbers.PhoneNumberType.UAN: "uan",
        phonenumbers.PhoneNumberType.VOICEMAIL: "voicemail",
        phonenumbers.PhoneNumberType.UNKNOWN: "unknown",
    }
    return {
        "e164": e164,
        "country_code": num.country_code,
        "national": phonenumbers.format_number(
            num, phonenumbers.PhoneNumberFormat.NATIONAL
        ),
        "region": region,
        "carrier": carrier,
        "line_type": line_map.get(line_type_raw, "unknown"),
        "timezones": list(
            phonenumbers.timezone.time_zones_for_number(num) or []
        ),
        "valid": True,
    }


def md5(s: str) -> str:
    return hashlib.md5(s.strip().lower().encode("utf-8")).hexdigest()


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
PYEOF
