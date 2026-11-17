"""Build the three PNG textures shipped inside the Blender extension.

Run with ordinary Python; Blender does not generate or pack marker images at runtime.
"""

from pathlib import Path
import struct
import zlib


ROOT = Path(__file__).resolve().parents[1] / "blender_fih_exporter" / "assets"
COLORS = {
    "Spawn": ((4, 31, 48), (32, 164, 245)),
    "Goal": ((7, 37, 16), (43, 197, 86)),
    "Checkpoint": ((48, 27, 3), (250, 151, 21)),
}
GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "N": ("10001", "11001", "10101", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
}


def _png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_texture(kind, path):
    dark, bright = COLORS[kind]
    pixels = bytearray((*dark, 255) * (256 * 256))

    def rect(x0, y0, x1, y1, color):
        for y in range(y0, y1):
            for x in range(x0, x1):
                if 0 <= x < 256 and 0 <= y < 256:
                    offset = (y * 256 + x) * 4
                    pixels[offset:offset + 4] = bytes((*color, 255))

    rect(0, 0, 256, 9, bright)
    rect(0, 247, 256, 256, bright)
    rect(0, 0, 9, 256, bright)
    rect(247, 0, 256, 256, bright)
    rect(16, 16, 240, 74, bright)
    label = kind.upper()
    scale = 3
    left = (256 - (len(label) * 6 - 1) * scale) // 2
    for index, char in enumerate(label):
        for row, bits in enumerate(GLYPHS[char]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    x = left + (index * 6 + col) * scale
                    y = 33 + row * scale
                    rect(x, y, x + scale, y + scale, (255, 255, 255))
    # Texture top maps to Blender +Y. Its arrow points down to local -Y,
    # which is the game's zero-yaw forward direction after axis conversion.
    rect(113, 110, 143, 162, (255, 255, 255))
    for y in range(151, 218):
        half_width = int((217 - y) * 0.67)
        rect(128 - half_width, y, 129 + half_width, y + 1, (255, 255, 255))

    rows = b"".join(b"\0" + pixels[y * 1024:(y + 1) * 1024] for y in range(256))
    data = (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(rows, level=9))
            + _png_chunk(b"IEND", b""))
    path.write_bytes(data)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for marker_kind in COLORS:
        target = ROOT / f"{marker_kind.lower()}.png"
        write_texture(marker_kind, target)
        print(target)
