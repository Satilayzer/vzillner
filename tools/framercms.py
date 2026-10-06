"""Codec for Framer bundled CMS files (*.framercms): item chunks and dictionary indexes.

Mirrors DatabaseValueModel / DatabaseItemModel / DatabaseDictionaryIndexModel from
Framer's generated collection module. All integers are big-endian.
"""
import json
import struct
from functools import cmp_to_key

NULL, ARRAY, BOOLEAN, COLOR, DATE, ENUM, FILE, LINK, NUMBER, OBJECT, IMAGE, RICHTEXT, STRING, VECTOR = range(14)


class Reader:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def take(self, n):
        b = self.d[self.o:self.o + n]
        assert len(b) == n, 'unexpected end of data'
        self.o += n
        return b

    def u8(self): return self.take(1)[0]
    def i8(self): return struct.unpack('>b', self.take(1))[0]
    def u16(self): return struct.unpack('>H', self.take(2))[0]
    def u32(self): return struct.unpack('>I', self.take(4))[0]
    def i64(self): return struct.unpack('>q', self.take(8))[0]
    def f64(self): return struct.unpack('>d', self.take(8))[0]
    def str(self): return self.take(self.u32()).decode('utf8')


class Writer:
    def __init__(self):
        self.b = bytearray()

    def u8(self, v): self.b += struct.pack('>B', v)
    def i8(self, v): self.b += struct.pack('>b', v)
    def u16(self, v): self.b += struct.pack('>H', v)
    def u32(self, v): self.b += struct.pack('>I', v)
    def i64(self, v): self.b += struct.pack('>q', v)
    def f64(self, v): self.b += struct.pack('>d', v)

    def str(self, s):
        e = s.encode('utf8')
        self.u32(len(e))
        self.b += e


# Values are kept as (type, payload) tuples; JSON payloads keep their raw string so
# re-encoding is byte-identical.
def read_value(r):
    t = r.u8()
    if t == NULL: return None
    if t == ARRAY: return (t, [read_value(r) for _ in range(r.u16())])
    if t == BOOLEAN: return (t, r.u8())
    if t in (COLOR, ENUM, FILE, STRING, LINK, IMAGE): return (t, r.str())
    if t == DATE: return (t, r.i64())
    if t == NUMBER: return (t, r.f64())
    if t == OBJECT: return (t, [(r.str(), read_value(r)) for _ in range(r.u16())])
    if t == RICHTEXT:
        k = r.i8()
        return (t, (k, r.u32() if k == 0 else r.str()))
    if t == VECTOR: return (t, r.u32())
    raise ValueError(f'unknown value type {t}')


def write_value(w, v):
    if v is None:
        w.u8(NULL)
        return
    t, p = v
    w.u8(t)
    if t == ARRAY:
        w.u16(len(p))
        for x in p: write_value(w, x)
    elif t == BOOLEAN: w.u8(p)
    elif t in (COLOR, ENUM, FILE, STRING, LINK, IMAGE): w.str(p)
    elif t == DATE: w.i64(p)
    elif t == NUMBER: w.f64(p)
    elif t == OBJECT:
        w.u16(len(p))
        for k, x in p:
            w.str(k)
            write_value(w, x)
    elif t == RICHTEXT:
        k, x = p
        w.i8(k)
        w.u32(x) if k == 0 else w.str(x)
    elif t == VECTOR: w.u32(p)
    else: raise ValueError(t)


def _cmp(a, b):
    return (a > b) - (a < b)


def _js(s):
    # JS compares strings by UTF-16 code units
    return s.encode('utf-16-be')


def compare_value(a, b, collation):
    ta = a[0] if a else NULL
    tb = b[0] if b else NULL
    if ta != tb: return _cmp(ta, tb)
    if a is None: return 0
    t, x, y = ta, a[1], b[1]
    if t == ARRAY:
        if len(x) != len(y): return _cmp(len(x), len(y))
        for p, q in zip(x, y):
            c = compare_value(p, q, collation)
            if c: return c
        return 0
    if t == OBJECT:
        dx, dy = dict(x), dict(y)
        kx, ky = sorted(dx), sorted(dy)
        if len(kx) != len(ky): return _cmp(len(kx), len(ky))
        for p, q in zip(kx, ky):
            if p != q: return _cmp(_js(p), _js(q))
            c = compare_value(dx[p], dy[q], collation)
            if c: return c
        return 0
    if t in (LINK, IMAGE):
        return _cmp(_js(json.dumps(json.loads(x), separators=(',', ':'), ensure_ascii=False)),
                    _js(json.dumps(json.loads(y), separators=(',', ':'), ensure_ascii=False)))
    if t == STRING:
        if collation.get('type') == 0:
            x, y = x.lower(), y.lower()
        return _cmp(_js(x), _js(y))
    if t in (COLOR, ENUM, FILE):
        return _cmp(_js(x), _js(y))
    if t == RICHTEXT:
        (kx, vx), (ky, vy) = x, y
        assert kx == ky
        return _cmp(_js(vx), _js(vy)) if kx == 1 else _cmp(vx, vy)
    return _cmp(x, y)


def read_chunk(data):
    """Returns list of items; each item is a list of (fieldName, value)."""
    r = Reader(data)
    items = []
    for _ in range(r.u32()):
        items.append([(r.str(), read_value(r)) for _ in range(r.u16())])
    assert r.o == len(data)
    return items


def write_chunk(items, chunk_id=0):
    """Returns (bytes, pointers) where pointers[i] = (chunkId, offset, length)."""
    w = Writer()
    w.u32(len(items))
    pointers = []
    for item in items:
        start = len(w.b)
        w.u16(len(item))
        for k, v in item:
            w.str(k)
            write_value(w, v)
        pointers.append((chunk_id, start, len(w.b) - start))
    return bytes(w.b), pointers


def read_index(data):
    r = Reader(data)
    collation_raw = r.str()
    names = [r.str() for _ in range(r.u8())]
    entries = []
    for _ in range(r.u32()):
        values = [read_value(r) for _ in names]
        entries.append((values, (r.u16(), r.u32(), r.u32())))
    assert r.o == len(data)
    return collation_raw, names, entries


def write_index(collation_raw, names, entries):
    collation = json.loads(collation_raw)

    def cmp(e1, e2):
        for a, b in zip(e1[0], e2[0]):
            c = compare_value(a, b, collation)
            if c: return c
        p, q = e1[1], e2[1]
        return _cmp(p[:2], q[:2])

    entries = sorted(entries, key=cmp_to_key(cmp))
    w = Writer()
    w.str(collation_raw)
    w.u8(len(names))
    for n in names: w.str(n)
    w.u32(len(entries))
    for values, ptr in entries:
        for v in values: write_value(w, v)
        w.u16(ptr[0]); w.u32(ptr[1]); w.u32(ptr[2])
    return bytes(w.b)


def build_index(collation_raw, names, items, pointers):
    entries = []
    for item, ptr in zip(items, pointers):
        d = dict(item)
        entries.append(([d.get(n) for n in names], ptr))
    return write_index(collation_raw, names, entries)
