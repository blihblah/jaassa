import gfxconvert


def convert_font(infname, outfname):
    # First, the text
    defchars, output = gfxconvert.create_charset(infname)
    colour = (1 << 4) + 2

    patterns = gfxconvert.batch_convert(defchars, colour)

    with open(outfname, 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)


def convert_sprite(infname, outfname):

    defchars, output = gfxconvert.create_charset(infname, orientation="vertical", redundancy=True)
    print("Defchar length", len(defchars))
    # ccoding, patterns = gfxconvert.rle_encode_graphics(defchars, (10, 0))
    colour = (15 << 4) + 12
    patterns = gfxconvert.batch_convert(defchars, colour)

    with open(outfname, 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)


def convert_titlescreen(infname, outfname_base):
    #infname = "../resources/general/gadventure_title.png"
    defchars, output = gfxconvert.create_charset(infname)
    ccoding, patterns = gfxconvert.rle_encode_graphics(defchars)

    base_offset = 0
    unpacked_scr = []
    for y in range(24):
        for x in range(32):
            unpacked_scr.append(output[(x, y)] + base_offset)
        print(unpacked_scr[-32:])

    outname = outfname_base + "_chars_rle.bin"
    with open(outname, 'wb') as f:
        scr_rle = gfxconvert.rle_encode_sequence(unpacked_scr)
        barr = bytes(scr_rle)
        f.write(barr)

    outname = outfname_base + ".bin"

    with open(outname, 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)

    outname = outfname_base + "_colours.bin"
    with open(outname, 'wb') as f:
        barr = bytes(ccoding)
        f.write(barr)


def convert_gamescreen(infname, outfname_base):
    defchars, output = gfxconvert.create_charset(infname)

    ccoding, patterns = gfxconvert.rle_encode_graphics(defchars)

    base_offset = 75

    unpacked_scr = []
    for y in range(24):
        for x in range(32):
            unpacked_scr.append(output[(x, y)] + base_offset)
        print(unpacked_scr[-32:])

    scr_rle = gfxconvert.rle_encode_sequence(unpacked_scr)

    outname = outfname_base + ".bin"
    with open(outname, 'wb') as f:
        barr = bytes(patterns)
        f.write(barr)

    outname = outfname_base + "_colours.bin"
    with open(outname, 'wb') as f:
        barr = bytes(ccoding)
        f.write(barr)

    outname = outfname_base + "_chars_rle.bin"
    with open(outname, 'wb') as f:
        barr = bytes(scr_rle)
        f.write(barr)
