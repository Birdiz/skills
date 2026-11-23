"""The flat YAML subset and the Markdown structure findings files use."""
import re

FENCE = re.compile(r"^(`{3,}|~{3,})")


# --- YAML: the flat subset the schema uses ---------------------------------

def scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text == "true":
        return True
    if text == "false":
        return False
    return text


def split_flow(text):
    parts, depth, quote, cur = [], 0, None, ""
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts]


def strip_comment(text):
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def value(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [scalar(p) for p in split_flow(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        out = {}
        for part in split_flow(text[1:-1]):
            if ":" not in part:
                raise ValueError("flow mapping entry without a colon: %s" % part)
            k, v = part.split(":", 1)
            out[k.strip()] = scalar(v)
        return out
    return scalar(text)


def parse_yaml(lines):
    """Returns (dict, [(line offset, message)])."""
    data, problems, key = {}, [], None
    for i, raw in enumerate(lines):
        line = strip_comment(raw)
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s+(.*))?$", line)
        if m:
            key = m.group(1)
            if key in data:
                problems.append((i, "key `%s` given twice" % key))
            try:
                data[key] = value(m.group(2)) if m.group(2) else []
            except ValueError as e:
                problems.append((i, str(e)))
            continue
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and key is not None and isinstance(data.get(key), list):
            data[key].append(scalar(m.group(1)))
            continue
        problems.append((i, "unreadable YAML line: %s" % raw.strip()))
    return data, problems


# --- Markdown structure ----------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def outside_fences(lines):
    """Yields (index, line, None, None) for each line outside fenced blocks,
    and (index of the opening fence, None, info string, body lines) for each block."""
    fence, start, info, body = None, 0, "", []
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if fence is None and m:
            fence, start, info, body = m.group(1), i, line[len(m.group(1)):].strip(), []
            continue
        if fence is not None:
            if line.strip().startswith(fence[0] * len(fence)) and line.strip().strip(fence[0]) == "":
                yield start, None, info, body
                fence = None
            else:
                body.append(line)
            continue
        yield i, line, None, None


def blocks(lines, level):
    """Splits lines by headings of the given level, fences ignored.
    Returns [(heading text or None, start index, [(index, line or None, info, body)])]."""
    mark = "#" * level + " "
    out = [(None, 0, [])]
    for item in outside_fences(lines):
        i, line = item[0], item[1]
        if line is not None and line.startswith(mark):
            out.append((line[len(mark):].strip(), i, []))
        elif line is not None and level == 3 and line.startswith("## "):
            out.append((None, i, []))
        else:
            out[-1][2].append(item)
    return out


def paragraphs(items):
    """Groups prose lines into paragraphs: [(index of first line, text)]."""
    out, cur, start = [], [], None
    for i, line, _, _ in items:
        if line is None or not line.strip():
            if cur:
                out.append((start, " ".join(cur)))
            cur, start = [], None
            continue
        if start is None:
            start = i
        cur.append(line.strip())
    if cur:
        out.append((start, " ".join(cur)))
    return out


def bullets(items):
    """Top-level list items: [(index, text)], continuation lines joined."""
    out = []
    for i, line, _, _ in items:
        if line is None:
            continue
        if re.match(r"^(-|\*|\d+\.)\s", line):
            out.append([i, line.strip()])
        elif out and line.strip() and (line.startswith(" ") or line.startswith("\t")):
            out[-1][1] += " " + line.strip()
        elif not line.strip():
            continue
        elif out and not line.startswith("#"):
            out.append([None, None])
    return [(i, t) for i, t in out if t is not None]


def label_of(paragraph):
    """The label of a prose section paragraph, `**<Label>.** …`, or None."""
    m = re.match(r"^\*\*([^*]+?)\.\*\*", paragraph)
    return m.group(1) if m else None
