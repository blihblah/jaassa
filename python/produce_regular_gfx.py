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
        #print(unpacked_scr[-32:])

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

def convert_fullscreen(infname, outfname_base):
    by_segment = gfxconvert.create_fullscreen(infname)
    total_screen = []
    #print("STARTING TO PRODUCE TITLE SCREEN:", infname)
    for area, val_d in sorted(by_segment.items()):
        defchars = val_d['chars']
        output = val_d['charmap']
        ccoding, patterns = gfxconvert.rle_encode_graphics(defchars)

        unpacked_scr = []
        for y in range(8):
            for x in range(32):
                unpacked_scr.append(output[(x, y)])
            #print(unpacked_scr[-32:])

        #outname = outfname_base + "_{}_chars_rle.bin".format(area)
        #with open(outname, 'wb') as f:
        #    scr_rle = gfxconvert.rle_encode_sequence(unpacked_scr)
        #    barr = bytes(scr_rle)
        #    f.write(barr)
        total_screen.extend(unpacked_scr)

        outname = outfname_base + "_{}.bin".format(area)

        with open(outname, 'wb') as f:
            barr = bytes(patterns)
            f.write(barr)

        outname = outfname_base + "_{}_colours.bin".format(area)
        with open(outname, 'wb') as f:
            barr = bytes(ccoding)
            f.write(barr)

    outname = outfname_base + "_chars.bin".format(area)
    with open(outname, 'wb') as f:
        barr = bytes(total_screen)
        f.write(barr)
    #print ("WROTE TITLE SCREEN:")
    #while total_screen:
    #    print(total_screen[:32])
    #    total_screen = total_screen[32:]
