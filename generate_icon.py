"""Generate LNG tank icon for the application (macOS .icns + PNG)."""
import struct
import zlib
import os

def create_png(width, height):
    """Create a simple LNG tank icon as PNG bytes."""
    # Simple tank shape: cylinder with dome top
    pixels = []
    cx, cy = width // 2, height // 2
    tank_w = width * 0.5
    tank_h = height * 0.55
    dome_h = height * 0.12

    for y in range(height):
        row = []
        for x in range(width):
            dx = x - cx
            dy = y - cy

            # Dome (top): half ellipse
            dome_y = cy - tank_h/2
            rel_y = y - dome_y
            if 0 <= rel_y <= dome_h:
                dome_rx = tank_w / 2 * (1 - (rel_y - dome_h/2) / (dome_h/2) ** 2) ** 0.5 if rel_y != dome_h/2 else tank_w / 2
                in_dome = abs(dx) <= max(1, dome_rx)
            else:
                in_dome = False

            # Cylinder body
            body_top = dome_y + dome_h
            body_bot = dome_y + tank_h
            in_body = body_top <= y <= body_bot and abs(dx) <= tank_w / 2

            # Base: flat bottom
            in_base = body_bot < y <= body_bot + height * 0.03 and abs(dx) <= tank_w / 2

            # Valve on top
            valve_w = 4
            valve_h = 8
            in_valve = (dome_y - valve_h) <= y <= dome_y and abs(dx) <= valve_w

            if in_valve:
                r, g, b, a = 180, 180, 190, 255
            elif in_dome or in_body or in_base:
                # Shading for 3D effect
                shade = 1.0 - abs(dx) / (tank_w / 2 + 1) * 0.3
                if in_dome:
                    shade *= 0.9
                r = int(70 * shade)
                g = int(130 * shade)
                b = int(180 * shade)
                a = 255
                # Highlight line
                if abs(dx) < 3:
                    r, g, b = min(255, r + 60), min(255, g + 60), min(255, b + 60)
                # Bottom edge
                if in_base:
                    r, g, b = r // 2, g // 2, b // 2
            else:
                r, g, b, a = 0, 0, 0, 0
            row.extend([r, g, b, a])
        pixels.extend(row)

    # Create PNG
    raw_data = bytes(pixels)

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # RGBA

    # Filter bytes (each row starts with 0 for no filter)
    raw = b'\x00' + b'\x00'.join(raw_data[i:i+width*4] for i in range(0, len(raw_data), width*4))
    compressed = zlib.compress(raw)

    png = signature + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')
    return png


def create_icns(png_128_data, png_256_data):
    """Create macOS .icns file from PNG data."""
    icon_types = [
        (b'ic07', png_128_data),  # 128x128
        (b'ic08', png_256_data),  # 256x256
    ]
    data = b'icns'
    entries = b''
    for itype, idata in icon_types:
        size = struct.pack('>I', len(idata) + 8)
        entries += itype + size + idata
    data += struct.pack('>I', len(entries) + 8) + entries
    return data


if __name__ == '__main__':
    out_dir = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(out_dir, exist_ok=True)

    png_128 = create_png(128, 128)
    png_256 = create_png(256, 256)

    with open(os.path.join(out_dir, 'icon_128.png'), 'wb') as f:
        f.write(png_128)
    with open(os.path.join(out_dir, 'icon_256.png'), 'wb') as f:
        f.write(png_256)
    with open(os.path.join(out_dir, 'icon.icns'), 'wb') as f:
        f.write(create_icns(png_128, png_256))

    print(f'Icons created in {out_dir}/')
