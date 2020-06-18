from PIL import Image


ALPHA = {(255, 255, 0, 255), (255, 255, 0)}


PALETTE_MAP = {
    (1, 1, 1, 255): 1,
    (62, 184, 73, 255): 2,
    (116, 208, 125, 255): 3,
    (89, 85, 224, 255): 4,
    (128, 118, 241, 255): 5,
    (185, 94, 81, 255): 6,
    (101, 219, 239, 255): 7,
    (219, 101, 89, 255): 8,
    (255, 137, 125, 255): 9,
    (204, 195, 94, 255): 10,
    (222, 208, 135, 255): 11,
    (58, 162, 65, 255): 12,
    (183, 102, 181, 255): 13,
    (204, 204, 204, 255): 14,
    (255, 255, 255, 255): 15
}

PALETTE_MAP.update(dict((tuple(k[:3]), v) for k, v in PALETTE_MAP.items()))


def split_char(char_entry):
    """
    Splits the char_entry as in defined_chars returned by create_charset()
    to pattern and colour tables.
    :param char_entry:
    :return:
    """
    pattern = []
    colours = []
    for b in range(0, 8 * 8, 8):
        row = char_entry[b:(b + 8)]
        row = [PALETTE_MAP[px] for px in row]
        cs = set(row)
        if len(cs) == 1:
            cols = [0, cs.pop()]
        else:
            cols = list(cs)
            cols.sort()
        bits = []
        for px in row:
            if px == cols[1]:
                bits.append("0")
            else:
                bits.append("1")
        pattern.append(int("".join(bits), 2))
        colours.append(16 * cols[0] + cols[1])
    return tuple(pattern), tuple(colours)


def create_charset(imgname, defined_chars=None, orientation="horizontal", redundancy=False):
    """
    Read a PNG file and convert it.
    """
    img = Image.open(imgname)
    w, h = img.size
    print("Read image size:", w, h)
    if defined_chars is None:
        defined_chars = {}

    n_key = len(defined_chars)
    actual_output = {}

    if orientation == "horizontal":
        for y0 in range(0, h, 8):
            for x0 in range(0, w, 8):
                ch = []
                for y in range(y0, y0 + 8):
                    for x in range(x0, x0 + 8):
                        px = img.getpixel((x, y))
                        if px in ALPHA:
                            break
                        ch.append(px)
                    if px in ALPHA:
                        break
                if px in ALPHA:
                    continue
                ch = tuple(ch)
                if ch not in defined_chars or redundancy:
                    key = n_key
                    n_key += 1
                    defined_chars[ch] = key
                actual_output[(x0 / 8, y0 / 8)] = defined_chars[ch]
    else:
        for x0 in range(0, w, 8):
            for y0 in range(0, h, 8):
                ch = []
                for y in range(y0, y0 + 8):
                    for x in range(x0, x0 + 8):
                        px = img.getpixel((x, y))
                        if px in ALPHA:
                            break
                        ch.append(px)
                    if px in ALPHA:
                        break
                if px in ALPHA:
                    continue
                ch = tuple(ch)
                if ch not in defined_chars or redundancy:
                    key = n_key
                    n_key += 1
                    defined_chars[ch] = key
                actual_output[(x0 / 8, y0 / 8)] = defined_chars[ch]
    print("Actual output size:", len(actual_output))
    return defined_chars, actual_output


def rle_encode_sequence(seq):
    colourcoding = []
    current_batch = None
    final_output = []
    for r in seq:
        final_output.append(r)
        if current_batch is None or current_batch[1] != r:
            if current_batch is not None:
                colourcoding.extend(current_batch)
            current_batch = [0, r]
        current_batch[0] += 1
        if current_batch[0] == 255:
            colourcoding.extend(current_batch)
            current_batch = None
    if current_batch is not None:
        colourcoding.extend(current_batch)

    colourcoding.append(0)
    return colourcoding


def convert_to_palette(defined_char, colours):
    """
    Take in a defined character and the colour encoding for each
    pixel row; return the character converted to binary using the
    colour mapping defined by colours.
    """

    pxs = []
    for i in range(0, 64, 8):
        pxs.append(defined_char[i:(i+8)])

    patterns = []
    for row, clr in zip(pxs, colours):
        as_bits = []
        for i in range(8):
            c = row[i]
            if PALETTE_MAP[c] == clr & 15:
                as_bits.append("0")
            else:
                as_bits.append("1")
        patterns.append(int("".join(as_bits), 2))
    return patterns


def batch_convert(defined_chars, clr):
    patterns = []
    invmap = dict((v, k) for k, v in defined_chars.items())

    c1 = clr >> 4

    for k, vall in sorted(invmap.items()):
        as_bits = []
        for i in range(0, 64, 8):
            v = vall[i:(i + 8)]
            for c in v:
                c = PALETTE_MAP[c]
                if c == c1:
                    as_bits.append("1")
                else:
                    as_bits.append("0")
                if len(as_bits) == 8:
                    patterns.append(int("".join(as_bits), 2))
                    as_bits = []
    return patterns


def rle_encode_graphics(defined_chars, first_color=(0, 0)):
    patterns = []
    colors = []
    invmap = dict((v, k) for k, v in defined_chars.items())

    prev_col = first_color
    for k, vall in sorted(invmap.items()):
        as_bits = []
        for i in range(0, 64, 8):
            v = vall[i:(i + 8)]
            c0 = PALETTE_MAP[min(v)]
            c1 = PALETTE_MAP[max(v)]
            c0, c1 = min(c0, c1), max(c0, c1)
            if c0 == c1 and c0 in prev_col:
                c0, c1 = prev_col
            for c in v:
                c = PALETTE_MAP[c]
                if c == c0:
                    as_bits.append("0")
                else:
                    as_bits.append("1")
                if len(as_bits) == 8:
                    patterns.append(int("".join(as_bits), 2))
                    as_bits = []
            colors.append(c0 + c1 * 16)
            prev_col = (c0, c1)
        colourcoding = rle_encode_sequence(colors)
    return colourcoding, patterns
