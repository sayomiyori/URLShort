"""Base62 encode/decode for positive integers (short code from auto-increment id)."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)


def encode(n: int) -> str:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return ALPHABET[0]
    out: list[str] = []
    x = n
    while x:
        x, r = divmod(x, BASE)
        out.append(ALPHABET[r])
    return "".join(reversed(out))


def decode(s: str) -> int:
    if not s:
        raise ValueError("empty string")
    n = 0
    for ch in s:
        idx = ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"invalid base62 character: {ch!r}")
        n = n * BASE + idx
    return n
