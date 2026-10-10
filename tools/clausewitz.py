"""Minimal reader for Paradox (Clausewitz) script files.

Used by validate.py to cross-check the mod's script files. Standard library only.
"""

import re

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|#[^\n]*|[{}=]|[<>]=?|[^\s{}=#"<>]+')


def tokens(text):
    """Yield (kind, value, start, end) tokens, skipping comments."""
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok.startswith("#"):
            continue
        if tok in "{}=":
            kind = tok
        elif tok.startswith('"'):
            kind = "str"
            tok = tok[1:-1]
        else:
            kind = "word"
        yield kind, tok, m.start(), m.end()


class Block:
    """A `key = { ... }` block, with source offsets of its braces."""

    def __init__(self, key, open_pos, parent):
        self.key = key
        self.open = open_pos  # offset of "{"
        self.close = None     # offset of "}"
        self.parent = parent
        self.entries = []     # (key, value) where value is a str or a Block

    def get(self, key, default=None):
        for k, v in self.entries:
            if k == key:
                return v
        return default

    def get_all(self, key):
        return [v for k, v in self.entries if k == key]

    def blocks(self):
        return [(k, v) for k, v in self.entries if isinstance(v, Block)]

    def values(self):
        """Bare words in a list block such as `categories = { a b }`."""
        return [k for k, v in self.entries if v is None]


class ParseError(Exception):
    pass


def parse(text):
    """Parse text into a root Block. Raises ParseError on unbalanced braces."""
    root = Block(None, -1, None)
    stack = [root]
    toks = list(tokens(text))
    i = 0
    while i < len(toks):
        kind, val, start, _ = toks[i]
        cur = stack[-1]
        if kind == "}":
            if len(stack) == 1:
                raise ParseError(f"unexpected '}}' at offset {start} (line {line_of(text, start)})")
            cur.close = start
            stack.pop()
            i += 1
            continue
        if kind == "{":
            # anonymous block, e.g. inside a list
            blk = Block(None, start, cur)
            cur.entries.append((None, blk))
            stack.append(blk)
            i += 1
            continue
        if kind == "=":
            raise ParseError(f"unexpected '=' at line {line_of(text, start)}")
        # key [op value]
        if i + 1 < len(toks) and toks[i + 1][0] in ("=",) or (
                i + 1 < len(toks) and toks[i + 1][1] in ("<", ">", "<=", ">=")):
            if i + 2 >= len(toks):
                raise ParseError(f"dangling '=' after {val!r} at line {line_of(text, start)}")
            vkind, vval, vstart, _ = toks[i + 2]
            if vkind == "{":
                blk = Block(val, vstart, cur)
                cur.entries.append((val, blk))
                stack.append(blk)
            elif vkind in ("word", "str"):
                cur.entries.append((val, vval))
            else:
                raise ParseError(f"bad value after {val!r} at line {line_of(text, start)}")
            i += 3
            continue
        cur.entries.append((val, None))
        i += 1
    if len(stack) != 1:
        raise ParseError(f"unclosed '{{' opened at line {line_of(text, stack[-1].open)}")
    return root


def line_of(text, offset):
    return text.count("\n", 0, max(offset, 0)) + 1

