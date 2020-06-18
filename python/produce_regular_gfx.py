import gfxconvert


def convert_font():
    # First, the text
    infname = "../resources/general/gadventure_text.png"
    defchars, output = gfxconvert.create_charset(infname)
    colour = (1 << 4) + 2

    patterns = gfxconvert.batch_convert(defchars, colour)

    with open("../src/incbins/gfx_chars.bin", 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)
        print("GFX chars bin length", len(barr))


def convert_sprite():
    infname = "../resources/general/gadventure_sprites.png"

    defchars, output = gfxconvert.create_charset(infname, orientation="vertical", redundancy=True)
    print("Defchar length", len(defchars))
    # ccoding, patterns = gfxconvert.rle_encode_graphics(defchars, (10, 0))
    colour = (15 << 4) + 12
    patterns = gfxconvert.batch_convert(defchars, colour)

    with open("../src/incbins/gfx_sprites.bin", 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)


def convert_titlescreen():
    infname = "../resources/general/gadventure_title.png"
    defchars, output = gfxconvert.create_charset(infname)
    ccoding, patterns = gfxconvert.rle_encode_graphics(defchars)

    base_offset = 0
    unpacked_scr = []
    for y in range(24):
        for x in range(32):
            unpacked_scr.append(output[(x, y)] + base_offset)
        print(unpacked_scr[-32:])

    with open("../src/incbins/gfx_titlerle.bin", 'wb') as f:
        scr_rle = gfxconvert.rle_encode_sequence(unpacked_scr)
        barr = bytes(scr_rle)
        f.write(barr)

    with open("../src/incbins/gfx_titlegfx.bin", 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)
    with open("../src/incbins/gfx_title_crle.bin", 'wb') as f:
        barr = bytes(ccoding)
        f.write(barr)


def convert_gamescreen():
    infname = "../resources/general/gadventure_ui.png"
    defchars, output = gfxconvert.create_charset(infname)

    ccoding, patterns = gfxconvert.rle_encode_graphics(defchars)

    base_offset = 75

    unpacked_scr = []
    for y in range(24):
        for x in range(32):
            unpacked_scr.append(output[(x, y)] + base_offset)
        print(unpacked_scr[-32:])

    scr_rle = gfxconvert.rle_encode_sequence(unpacked_scr)

    with open("../src/incbins/gfx_ui.bin", 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)
        print("UI gfx.bin len", len(barr))
    with open("../src/incbins/gfx_ui_colours.bin", 'wb') as f:
        barr = bytes(ccoding)
        f.write(barr)
        print("UI rle colours.bin len", len(barr))

    with open("../src/incbins/gfx_ui_chars_rle.bin", 'wb') as f:
        barr = bytes(scr_rle)
        print("UI chars rle len", len(barr))
        f.write(barr)


def main():
    convert_font()
    convert_gamescreen()
    convert_sprite()
    convert_titlescreen()


if __name__ == "__main__":
    main()
