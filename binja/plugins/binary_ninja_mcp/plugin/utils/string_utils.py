def escape_non_ascii(input_str: str) -> str:
    """Escape non-ASCII characters in a string"""
    if input_str is None:
        return ""
    result = ""
    for c in input_str:
        if 32 <= ord(c) < 127:
            result += c
        else:
            result += f"\\x{ord(c):02x}"
    return result


def parse_int_or_default(val: str, default: int) -> int:
    """Parse an integer from a string or return a default value"""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
