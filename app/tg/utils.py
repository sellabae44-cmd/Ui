import re
TON_ADDR_RE = re.compile(r"^(EQ|UQ)[A-Za-z0-9_-]{40,110}$")
def looks_like_ton_address(s: str) -> bool:
    return bool(TON_ADDR_RE.match((s or '').strip()))
