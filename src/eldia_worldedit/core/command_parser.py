"""Tokenizer and WorldEdit-style flag parser (-a, -ae, -m mask, negative numbers)."""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"^-\d+(?:\.\d+)?$")


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split text by `sep` outside [...], (...), and quotes."""
    parts: list[str] = []
    buf: list[str] = []
    bracket_depth = 0
    paren_depth = 0
    quote: str | None = None
    for ch in text:
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
            continue
        if ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == sep and bracket_depth == 0 and paren_depth == 0:
            item = "".join(buf).strip()
            if item:
                parts.append(item)
            buf.clear()
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def tokenize_args(raw: str) -> list[str]:
    """Split a command argument string preserving quoted substrings without breaking WorldEdit tokens."""
    tokens: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if quote is not None:
            if ch == "\\" and i + 1 < n and raw[i + 1] in (quote, "\\"):
                buf.append(raw[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch in ('"', "'") and not buf:
            quote = ch
            i += 1
            continue
        if ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            i += 1
            continue
        buf.append(ch)
        i += 1

    if quote is not None:
        raise ValueError("Unterminated quoted argument.")
    if buf:
        tokens.append("".join(buf))
    return tokens


def parse_flags(
    tokens: list[str],
    value_flags: set[str] | None = None,
    bool_flags: set[str] | None = None,
) -> tuple[set[str], dict[str, str], list[str]]:
    """Parse WorldEdit flags from tokens while preserving negative numbers like -10 or -3.5.

    Returns (active_bool_flags, value_flag_map, positional_args).
    """
    vflags = value_flags or set()
    bflags = bool_flags or set()
    active: set[str] = set()
    values: dict[str, str] = {}
    positional: list[str] = []

    i = 0
    stop_flags = False
    while i < len(tokens):
        tok = tokens[i]
        if stop_flags:
            positional.append(tok)
            i += 1
            continue
        if tok == "--":
            stop_flags = True
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1 and not _NUMBER_RE.match(tok):
            flag_chars = tok[1:]
            if len(flag_chars) == 1 and flag_chars in vflags:
                if i + 1 >= len(tokens):
                    raise ValueError(f"Flag '-{flag_chars}' requires a value.")
                values[flag_chars] = tokens[i + 1]
                i += 2
                continue
            # Combined flags like -ae or -am <mask>
            valid_cluster = all(c.isalpha() for c in flag_chars)
            if valid_cluster:
                consumed_value = False
                for idx, ch in enumerate(flag_chars):
                    if ch in vflags:
                        if idx != len(flag_chars) - 1:
                            raise ValueError(f"Value flag '-{ch}' must be last in '-{flag_chars}'.")
                        if i + 1 >= len(tokens):
                            raise ValueError(f"Flag '-{ch}' requires a value.")
                        values[ch] = tokens[i + 1]
                        i += 2
                        consumed_value = True
                        break
                    if not bflags or ch in bflags:
                        active.add(ch)
                    else:
                        raise ValueError(f"Unknown flag '-{ch}'.")
                if not consumed_value:
                    i += 1
                continue
        positional.append(tok)
        i += 1

    return active, values, positional
