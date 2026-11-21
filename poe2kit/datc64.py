"""Read Path of Exile 2 data tables (.datc64) using the community dat-schema (poe-tool-dev/dat-schema).

Read-only: works on files already extracted from the installed game by poe2x (the game is never touched
while running, and nothing is written back). Layout of a .datc64:
    u32 row_count | row_count fixed-size rows | 8 x 0xBB marker | variable data (strings, arrays)
The schema gives each table's columns; the row width check (schema vs file) tells us if the schema is
out of date for that table, and we report it instead of returning garbage."""

import json
import os
import struct

from . import config

SCHEMA = config.SCHEMA_PATH
MARKER = b'\xbb' * 8
NULL64 = 0xFEFEFEFEFEFEFEFE

SIZES = {'bool': 1, 'i16': 2, 'u16': 2, 'i32': 4, 'u32': 4, 'f32': 4, 'enumrow': 4,
         'string': 8, 'row': 8, 'foreignrow': 16, 'array': 16, 'i64': 8, 'u64': 8}
FMT = {'bool': '<?', 'i16': '<h', 'u16': '<H', 'i32': '<i', 'u32': '<I', 'f32': '<f', 'enumrow': '<i',
       'i64': '<q', 'u64': '<Q'}

_schema = None


def schema():
    global _schema
    if _schema is None:
        with open(SCHEMA, encoding='utf-8') as f:
            d = json.load(f)
        tables = {}
        for t in d['tables']:
            if t.get('validFor', 3) & 2:  # 2 = PoE 2
                tables[t['name'].lower()] = t
        _schema = tables
    return _schema


def col_size(c):
    if c.get('array'):
        return 16
    if c.get('interval'):
        return 2 * SIZES.get(c['type'], 4)
    return SIZES[c['type']]


class TableError(Exception):
    pass


class Table:
    def __init__(self, path, name=None):
        self.path = path
        self.name = name or os.path.splitext(os.path.basename(path))[0]
        t = schema().get(self.name.lower())
        if not t:
            raise TableError(f'{self.name}: not in schema')
        self.columns = t['columns']
        with open(path, 'rb') as f:
            self.data = f.read()
        self.rows = struct.unpack_from('<I', self.data, 0)[0]
        self.var = self.data.find(MARKER)
        if self.var < 0:
            raise TableError(f'{self.name}: no data marker')
        self.width = (self.var - 4) // self.rows if self.rows else 0
        self.schema_width = sum(col_size(c) for c in self.columns)
        self.exact = self.width == self.schema_width

    def _string(self, off):
        start = self.var + off
        end = start
        while end + 4 <= len(self.data) and self.data[end:end + 4] != b'\0\0\0\0':
            end += 2
        try:
            return self.data[start:end].decode('utf-16-le')
        except UnicodeDecodeError:
            return None

    def _scalar(self, typ, buf, pos):
        if typ == 'string':
            return self._string(struct.unpack_from('<Q', buf, pos)[0])
        if typ == 'row':
            v = struct.unpack_from('<Q', buf, pos)[0]
            return None if v == NULL64 else v
        if typ == 'foreignrow':
            v = struct.unpack_from('<Q', buf, pos)[0]
            return None if v == NULL64 else v
        if typ in FMT:
            return struct.unpack_from(FMT[typ], buf, pos)[0]
        return None

    def _value(self, c, pos):
        d = self.data
        if c.get('array') or c['type'] == 'array':
            n, off = struct.unpack_from('<QQ', d, pos)
            et = c['type'] if c.get('array') else None
            if et is None or n > 100000:
                return [] if n == 0 else {'unknown_array': n}
            size = SIZES[et]
            base = self.var + off
            return [self._scalar(et, d, base + i * size) for i in range(n)]
        if c.get('interval'):
            s = SIZES.get(c['type'], 4)
            return [self._scalar(c['type'], d, pos), self._scalar(c['type'], d, pos + s)]
        return self._scalar(c['type'], d, pos)

    def __iter__(self):
        if not self.exact:
            raise TableError(f'{self.name}: schema row width {self.schema_width} != file {self.width} '
                             '(schema out of date for this table)')
        for r in range(self.rows):
            pos = 4 + r * self.width
            row = {}
            for i, c in enumerate(self.columns):
                name = c.get('name') or f'_unk{i}'
                try:
                    row[name] = self._value(c, pos)
                except (struct.error, KeyError):
                    row[name] = None
                pos += col_size(c)
            yield row

    def to_list(self):
        return list(self)


def dump_folder(src_dir, out_dir, only=None):
    """Convert every .datc64 in src_dir (recursively) to JSON in out_dir. Returns a report."""
    """English tables (the top folder) go straight into out_dir; translated copies the game ships in
    language subfolders (french, german, ...) go into out_dir/<language>/ so they never overwrite English."""
    os.makedirs(out_dir, exist_ok=True)
    report = {'ok': [], 'empty': [], 'schema_mismatch': [], 'not_in_schema': [], 'errors': [], 'languages': []}
    for root, _, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        lang = None if rel == '.' else rel.replace(os.sep, '/')
        dest = out_dir if lang is None else os.path.join(out_dir, lang)
        if lang and lang not in report['languages']:
            report['languages'].append(lang)
        for fn in files:
            if not fn.endswith('.datc64'):
                continue
            name = fn[:-7]
            if only and name.lower() not in only:
                continue
            p = os.path.join(root, fn)
            tag = name if lang is None else f'{lang}/{name}'
            try:
                t = Table(p, name)
                if t.rows == 0:
                    report['empty'].append(tag)
                    continue
                if not t.exact:
                    report['schema_mismatch'].append(f'{tag} (schema {t.schema_width} vs file {t.width})')
                    continue
                os.makedirs(dest, exist_ok=True)
                with open(os.path.join(dest, name + '.json'), 'w', encoding='utf-8') as f:
                    json.dump(t.to_list(), f, ensure_ascii=False)
                if lang is None:
                    report['ok'].append(f'{name} ({t.rows} rows)')
            except TableError as e:
                (report['not_in_schema'] if 'not in schema' in str(e) else report['errors']).append(str(e))
            except Exception as e:  # keep going; one bad table shouldn't stop the sweep
                report['errors'].append(f'{name}: {type(e).__name__}: {e}')
    return report
