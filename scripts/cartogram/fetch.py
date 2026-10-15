"""Download the official INEGI inputs for the cartogram into CACHE_DIR.

- Census 2020 population (ITER, 36.6 MB).
- Census 2020 municipal boundaries (Marco Geoestadistico 2020, layer 00mun).
  INEGI ships them inside a 3.1 GB zip that contains a 257 MB *stored* zip.
  Both are read in place with HTTP Range requests, so only ~40 MB is downloaded.
"""
import io
import os
import struct
import urllib.request
import zipfile
from pathlib import Path

CACHE = Path(os.environ.get('CACHE_DIR', Path.home() / '.cache/martinme-cartogram')) / 'data'
ITER_URL = 'https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/iter/iter_00_cpv2020_csv.zip'
MG_URL = ('https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/'
          'productos/geografia/marcogeo/889463807469/889463807469_s.zip')
MG_INNER = 'MG_2020_Integrado.zip'


def http_range(url, start, end):
    req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
    return urllib.request.urlopen(req).read()


class RemoteWindow(io.RawIOBase):
    """Seekable, read-only view of bytes [base, base + size) of a remote file."""

    def __init__(self, url, base=0, size=None):
        self.url, self.base, self.pos = url, base, 0
        if size is None:
            head = urllib.request.urlopen(urllib.request.Request(url, method='HEAD'))
            size = int(head.headers['Content-Length'])
        self.size = size

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buffer):
        if self.pos >= self.size:
            return 0
        n = min(len(buffer), self.size - self.pos)
        data = http_range(self.url, self.base + self.pos, self.base + self.pos + n - 1)
        buffer[:len(data)] = data
        self.pos += len(data)
        return len(data)


def open_remote_zip(window):
    return zipfile.ZipFile(io.BufferedReader(window, buffer_size=1 << 16))


def fetch_iter():
    target = CACHE / 'iter_00_cpv2020_csv.zip'
    if not target.exists():
        urllib.request.urlretrieve(ITER_URL, target)
    with zipfile.ZipFile(target) as z:
        z.extractall(CACHE / 'iter')


def fetch_municipios():
    out = CACHE / 'mg2020'
    out.mkdir(exist_ok=True)
    if (out / '00mun.shp').exists():
        return
    outer = open_remote_zip(RemoteWindow(MG_URL))
    info = outer.getinfo(MG_INNER)
    assert info.compress_type == zipfile.ZIP_STORED, 'inner zip must be stored to read it in place'
    header = http_range(MG_URL, info.header_offset, info.header_offset + 29)
    name_len, extra_len = struct.unpack('<HH', header[26:30])
    data_start = info.header_offset + 30 + name_len + extra_len
    inner = open_remote_zip(RemoteWindow(MG_URL, data_start, info.compress_size))
    for member in inner.infolist():
        name = member.filename.split('/')[-1]
        if name.startswith('00mun.'):
            (out / name).write_bytes(inner.read(member))


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    fetch_iter()
    fetch_municipios()
    print('inputs ready in', CACHE)
