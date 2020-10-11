import os
from collections import OrderedDict

import gfxconvert
import huffmanencoder
import produce_regular_gfx

"""
TODO:
- separate location gfx record (14*14 bytes)
- sort gfx tiles by total frequency, then compress them
- "stable" code for items (to avoid RAM storing, point location to starting location)

"""

from configparser import ConfigParser

CODE_NEWLINE = 2
CODE_UPPERCASE = 1
CODE_TERMINATOR = 0

CODE_ALPHA = dict((c, ord(c) - ord('a') + 3)
                  for c in "abcdefghijklmnopqrstuvwxyz")
CODE_ALPHA.update(dict((c, ord(c) - ord('A') + 3)
                       for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
CODE_ALPHA.update(dict((c, len(CODE_ALPHA) + i + 3) for i, c in enumerate(" 0123456789;:.,-!?'\"")))

LABELTEMPLATE_TEXT = "__TXT_{}"
LABELTEMPLATE_ITEM = "__ITEM_{}"
LABELTEMPLATE_LOCATION = "__LOCATION_{}"
LABELTEMPLATE_SCRIPT = "__S_{}"
LABELTEMPLATE_PALETTE = "__PALETTE_{}"
LABELTEMPLATE_ITEM_RAM = "__ITEMRAM_{}"
LABELTEMPLATE_GRAPHICSVIEW = "___GFXVIEW_{}"
CFG_SCRIPT_HEAD = "script_"
CFG_ITEM_HEAD = "item_"
CFG_LOCATION_HEAD = "location_"

TC_PLAYER_LOC = "_CURRENT"
TC_LOST_LOC = "_LOST"
TC_INVENTORY_LOC = "_INVENTORY"

CONSTANT_MAP = {
    TC_PLAYER_LOC: "$0001",
    TC_LOST_LOC: "$0000",
    TC_INVENTORY_LOC: "$0002"
}

COMMAND_MAP = {
    "END": 0,
    "GOTO": 1,
    "SETITEMLOC": 2,
    "TEXT": 3,
    "IFTRUE": 4,
    "SET": 5,
    "ISLOC": 6,
    "ISSTATE": 7,
    "SETTILE": 8,
    "GOEND": 9,
    "TEXTEND": 10,
    "TAKE": 11,
    "TAKEEND": 12,
    "ISOBJECT": 13,
    "LOCATIONTEXTEND": 14,
    "WAITFORFIRE": 15
}

# TODO: Consider making these easier to change.
DIRECTION_VALUES = {
    "here": 0,
    "north": 1,
    "east": 2,
    "south": 3,
    "west": 4,
    "up": 5,
    "down": 6,
    "inside": 7,
    "outside": 8,
    "back": 9,

}

# TODO: Consider making these easier to change.
PLAYER_COMMANDS = {
    "go": 0,
    "look": 1,
    "take": 2,
    "put": 3,
    "use": 4,
    "drop": 5,
    "examine": 6,
    "talk": 7,
    "talk about": 8,
    "buy": 9,
    "eat": 10,
    "ponder": 11,

}

VOID_LOCATION = "VOID"
INV_LOCATION = "INVENTORY"

LINE_LENGTH = 32 - 2


def wordwrap_text(s):
    """
    Apply very simple wordwrap -- add extra spaces at the end of the lines.
    Wastes space, but was simple to implement.
    """
    res = []

    row = ""
    for v in s.split():
        rowlen = len(row) + len(v) + 1
        if rowlen > LINE_LENGTH:
            pad = LINE_LENGTH - len(row)
            res.append(row + " " * pad)
            row = v
        else:
            if len(row) >= 1:
                row = row + " " + v
            else:
                row = v
    res.append(row)
    return "".join(res)


def encode_text(s):
    """
    Convert a string to a sequence of characters
    to pack.
    """
    s = wordwrap_text(s)
    res = []
    for c in s:
        if c == "\\":
            res.append(CODE_NEWLINE)
            continue
        elif c.upper() == c and c.lower() != c:
            res.append(CODE_UPPERCASE)
        res.append(CODE_ALPHA[c])
    if len(res) == 0:
        res.append(CODE_ALPHA[' '])
    res.append(CODE_TERMINATOR)
    return bytes(res)


def write_direction_names(data, fname):
    """
    Write the compressed strings for each direction into a file ready for
    inclusion in the ASM source code.
    """
    with open(fname, 'w') as f:
        f.write(";; Direction names.\n")
        dnames = []
        for k, v in sorted([(b, a) for (a, b) in DIRECTION_VALUES.items()]):
            lbl = "__DIRNAME_{}".format(v)
            dnames.append(lbl)
            enc = encode_text(v)
            f.write("{}:\n".format(lbl))
            write_compressed_string(data, f, enc, v)
        f.write("DIRECTION_NAMES:\n")
        f.write("DW {}\n".format(", ".join(dnames)))


def write_command_names(data, fname):
    """
    Write the compressed strings for each direction into a file ready for
    inclusion in the ASM source code.
    """
    with open(fname, 'w') as f:
        f.write(";; Command names.\n")
        dnames = []
        for k, v in sorted([(b, a) for (a, b) in PLAYER_COMMANDS.items()]):
            lbl1 = v.replace(" ", "_")

            lbl = "__CMDNAME_{}".format(lbl1)
            dnames.append(lbl)
            enc = encode_text(v)
            f.write("{}:\n".format(lbl))
            write_compressed_string(data, f, enc, v)
        f.write("COMMAND_NAMES:\n")
        f.write("DW {}\n".format(", ".join(dnames)))


def write_texts(cfg, data, fname):
    """
    Writes the items under [text] section.
    """
    d = cfg['text']
    with open(fname, 'w') as f:
        f.write(";; Strings compressed \n")
        for k, v_orig in d.items():
            v = encode_text(v_orig)
            f.write("{}: ;;\n".format(LABELTEMPLATE_TEXT.format(k)))
            write_compressed_string(data, f, v, v_orig)


def generate_huffdict(cfg, data, out_fname):
    """
    Generate the huffdict from the strings in all_inputs.
    """

    all_inputs = extract_displayed_strings(cfg, data)

    total_string = b""
    for j in all_inputs:
        total_string = total_string + encode_text(j)
    dictionary = huffmanencoder.create_dictionary(total_string)
    data['huffdict'] = dictionary

    huffmanencoder.write_dictionary(dictionary, out_fname)


def extract_displayed_strings(cfg, data):
    """
    Extract all different strings that will be stored.
    """
    res = []
    for key in cfg['text']:
        res.append(cfg['text'][key])

    res.extend(PLAYER_COMMANDS.keys())
    res.extend(DIRECTION_VALUES.keys())

    return res


def parse_scriptfile(data, infilename):
    scripts = {}
    current_script = None
    valid_ends = [COMMAND_MAP[s] for s in ("END", "GOEND", "TEXTEND", "TAKEEND", "LOCATIONTEXTEND")]
    with open(infilename, 'r') as f:
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            if line.startswith("#") or line.startswith(";"):
                continue

            parts = line.split()
            cmd = parts[0].upper()

            cmdval = COMMAND_MAP.get(cmd, None)

            if cmd == "END":
                current_script.append((cmdval,))
            elif cmd == "GOTO":
                current_script.append((cmdval, parts[1]))
            elif cmd == "SETITEMLOC":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "TEXT":
                current_script.append((cmdval, parts[1]))
            elif cmd == "IFTRUE":
                # parts[1] should be a script name
                current_script.append((cmdval, parts[1]))
            elif cmd == "SET":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "ISLOC":
                current_script.append((cmdval, parts[1]))
            elif cmd == "ISSTATE":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "SETTILE":
                current_script.append((cmdval, parts[1], parts[2], parts[3]))
            elif cmd == "GOEND":
                current_script.append((cmdval, parts[1]))
            elif cmd == "TEXTEND":
                current_script.append((cmdval, parts[1]))
            elif cmd == "TAKE":
                current_script.append((cmdval, parts[1]))
            elif cmd == "TAKEEND":
                current_script.append((cmdval, parts[1]))
            elif cmd == "ISOBJECT":
                current_script.append((cmdval, parts[1]))
            elif cmd == "LOCATIONTEXTEND":
                current_script.append((cmdval,))
            elif cmd == "WAITFORFIRE":
                current_script.append((cmdval,))
            elif cmd.startswith("SCRIPT"):
                if current_script is not None:
                    if current_script[-1][0] not in valid_ends:
                        print("NO END COMMAND", script_name)
                        assert 1 == 0

                # Start new script.
                current_script = []
                script_name = parts[1][:-1]
                scripts[script_name] = current_script
            else:
                print("CMD", repr(cmd))
                assert 1 == 0  # Unknown command
    data['scripts'] = scripts


def write_script(data, script_commands, outfn):
    """
    Write the script commands in the parameter.
    :param outfn:
    :param data:
    :param script_commands:
    """

    with open(outfn, "w") as f:
        f.write(";;; Game scripts \n")
        for script, cmds in script_commands.items():
            f.write("  {}: ;; Script {}\n".format(as_scriptlabel(script), script))
            for cmd in cmds:
                f.write("  DB {}\n".format(cmd[0]))
                if cmd[0] == 0:  # END
                    pass
                elif cmd[0] == 1:  # GOTO
                    f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                elif cmd[0] == 2:  # SETITEMLOC
                    f.write("    DW {}, {}\n".format(as_itemlabel(cmd[1]),
                                                     as_locationlabel(cmd[2])))
                elif cmd[0] == 3:  # TEXT
                    f.write("    DW {}\n".format(as_textlabel(cmd[1])))
                elif cmd[0] == 4:  # IFTRUE
                    f.write("    DW {}\n".format(as_scriptlabel(cmd[1])))
                elif cmd[0] == 5:  # SET
                    f.write("    DB {}\n    DB {}\n".format(
                        cmd[1], cmd[2]
                    ))
                elif cmd[0] == 6:  # ISLOC
                    f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                elif cmd[0] == 7:  # ISSTATE
                    f.write("    DB {}, {}\n".format(cmd[1], cmd[2]))
                elif cmd[0] == 8:  # SETTILE
                    f.write("    DB {}, {}, {}, {}\n".format(*cmd[1:5]))
                elif cmd[0] == 9:  # GOEND
                    f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                elif cmd[0] == 10:  # TEXTEND
                    f.write("    DW {}\n".format(as_textlabel(cmd[1])))
                elif cmd[0] == 11:  # TAKE
                    f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                elif cmd[0] == 12:  # TAKEEND
                    f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                elif cmd[0] == 13:  # ISOBJECT
                    if cmd[1] in data['items']:
                        f.write("    DB {}\n".format('C_ITEM_INVENTORY_ICON'))
                        f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                    else:
                        d_ind = DIRECTION_VALUES[cmd[1].lower()]
                        f.write("    DB {}, {}, 0\n".format(
                            'C_ITEM_DIRECTION', d_ind))
            f.write("\n\n")


def read_input(cfg):
    data_collection = {
        'locations': OrderedDict(),
        'items': OrderedDict(),
        'graphics': {
            'defined_chars': {}
        },
        'used_texts': set([]),
        'used_scripts': set([]),
        'scripts': {},
        'gfxviews': {}
    }
    print("Reading input")
    for s in cfg.sections():
        print(s)
        if s.startswith(CFG_LOCATION_HEAD):
            parse_location(data_collection, cfg, s)
        elif s.startswith(CFG_ITEM_HEAD):
            parse_item(data_collection, cfg, s)
    parse_scriptfile(data_collection, cfg['in_files']['scripts'])
    return data_collection


def as_textlabel(s):
    return LABELTEMPLATE_TEXT.format(s)


def as_scriptlabel(s):
    return LABELTEMPLATE_SCRIPT.format(s)


def as_itemlabel(s):
    return LABELTEMPLATE_ITEM.format(s)


def as_itemlabel_RAM(s):
    return LABELTEMPLATE_ITEM_RAM.format(s)


def as_locationlabel(s):
    if s not in CONSTANT_MAP:
        return LABELTEMPLATE_LOCATION.format(s)
    else:
        return CONSTANT_MAP[s]


def as_palettelabel(s):
    return LABELTEMPLATE_PALETTE.format(s)

def as_graphicsviewlabel(s):
    return LABELTEMPLATE_GRAPHICSVIEW.format(s)


def intlist_to_string(s):
    return [str(i) for i in s]


def parse_location(data, cfg, loc_key):
    # cfg = ConfigParser()
    loc_name = loc_key[len(CFG_LOCATION_HEAD):]
    gfx_file = cfg.get(loc_key, 'gfx')
    defined_chars = data['graphics']['defined_chars']
    defined_chars, tiles = gfxconvert.create_charset(gfx_file, defined_chars)
    print("Created tiles.")
    loc = {'scripts': {}}
    data['locations'][loc_name] = loc
    loc['gfx'] = tiles
    text_key = cfg.get(loc_key, 'description')
    data['used_texts'].add(text_key)
    loc['description'] = text_key
    for k in cfg[loc_key]:
        if k.startswith(CFG_SCRIPT_HEAD):
            rest = k[len(CFG_SCRIPT_HEAD):]
            dname, cmd = rest.split("_")
            for d in DIRECTION_VALUES:
                if dname.lower() == d.lower():
                    print("Found command", dname, cmd)

                    if d not in loc['scripts']:
                        loc['scripts'][d] = {}
                    loc['scripts'][d][cmd] = cfg[loc_key][k]
                    data['used_scripts'].add(cfg[loc_key][k])
    if "entrancescript" in cfg[loc_key]:
        loc['entrancescript'] = cfg.get(loc_key, "entrancescript")
        data['used_scripts'].add(cfg.get(loc_key, "entrancescript"))
    else:
        loc['entrancescript'] = "DefaultEntryScript"
        data['used_scripts'].add("DefaultEntryScript")


def prepare_graphics(cfg, data):
    """
    Prepare the graphics tiles to a binary.
    """
    # TODO: Optimize and create multiple "palettes"!
    for loc_name in data['locations']:
        # Create a list of all tiles we're using in this feature.
        # Then create a palette.
        used_orig_tiles = data['locations'][loc_name]['gfx']

        locgfx = LocationGraphics()
        locgfx.original_tiles = used_orig_tiles
        data['locations'][loc_name]['locgfx'] = locgfx
        data['gfxviews'][loc_name] = locgfx


def write_palettes(cfg, data, fname):
    with open(fname, 'w') as f:
        f.write(";; Palettes for locations.\n")
        for loc_name, loc_d in data['locations'].items():
            locgfx = loc_d['locgfx']
            ctvd, palette = locgfx.convert()
            f.write("{}:\nDB ".format(as_palettelabel(loc_name)))
            encoded = palette.encode()
            f.write(", ".join(["$" + ("00" + hex(v)[2:])[-2:] for v in encoded]) + "\n")

def write_graphicsview(cfg, data, fname):
    with open(fname, 'w') as f:
        f.write(";; Graphics views\n")
        for gfx_name, gfx_d in data['gfxviews'].items():
            ctvd, palette = gfx_d.convert()
            f.write("{}:\n".format(as_graphicsviewlabel(gfx_name)))
            for y in range(14):
                f.write("DB ")
                for x in range(14):
                    if x > 0:
                        f.write(", ")
                    f.write("{}".format(ctvd[(x, y)]))
                f.write("\n")


class Palette(object):
    def __init__(self):
        self.tile2palette = {}
        self.palette2tile = {}
        self.straights = []

    def add_tile2palette(self, tile, val):
        self.tile2palette[tile] = val
        self.palette2tile[val] = tile

    def unwrap_straights(self):
        counter = 0
        for s in self.straights:
            for i in range(s[0], s[1]):
                self.add_tile2palette(i, counter)
                counter += 1

    def encode(self):
        # Presumes format:
        # [bytes skipped][bytes included][$ff]
        coded = []
        prev_end = -1
        for i, s in enumerate(self.straights):
            skipped = 0
            if s[0] > prev_end:
                skipped = s[0] - prev_end - 1
            length = s[1] - s[0]
            prev_end = s[1] - 1

            while skipped > 254:
                coded.extend([254, 0])
                skipped -= 254

            # Length cannot be longer than 254, so this bit is easy.
            coded.extend([skipped, length])
        coded.append(255)
        return coded

    def decode(self):
        vd = {}
        c = 0
        for s in self.straights:
            for r in range(s[0], s[1]):
                vd[c] = r
                c += 1
        return vd


class LocationGraphics(object):
    def __init__(self):
        self.original_tiles = None
        self.palette = None

    def create_palette(self, tiles):
        # Palette format:
        # [bytes skipped][bytes included][$ff]
        tiles_used = set([])
        for (x, y), val in tiles.items():
            tiles_used.add(val)
        unpruned_palette = list(tiles_used)
        unpruned_palette.sort()

        p = Palette()
        straights = []
        prev = -1
        first = -1
        for i, v in enumerate(unpruned_palette):
            if prev == -1:
                # Insert gap.
                prev = v
                first = v
            elif prev == v - 1:
                # Straight continues
                prev = v
                continue
            else:
                straights.append((first, prev + 1))
                prev = v
                first = v
        straights.append((first, prev + 1))
        p.straights = straights
        p.unwrap_straights()
        return p

    def convert(self):
        if self.palette is None:
            palette = self.create_palette(self.original_tiles)
            self.palette = palette
        else:
            palette = self.palette
        converted = {}
        for y in range(14):
            for x in range(14):
                converted[(x, y)] = palette.tile2palette[self.original_tiles[(x, y)]]
        return converted, palette


def write_locations(data, outfn):
    """
    ;; Location records: 10 + 14*14 + 1 + 3*3 = 216
    ;; [description, compressed]
    ;; [gfx tiles, fixed size]
    ;; [how many directions [byte]]
    ;; [direction_code][script pointer] * num_of_directions
    ;; [commands to alter the looks]
    """
    with open(outfn, 'w') as f:
        for loc, d in data['locations'].items():
            f.write("{}:\n".format(as_locationlabel(loc)))
            # Now, link to description.
            f.write("DW {}  ;; Location description\n".format(
                as_textlabel(d['description'])))
            # Which tile dictionary to use (2 bytes)
            # TODO: move this to the graphics data as well?
            f.write("DW {} ;; Start of tile dictionary location\n".format(
                as_palettelabel(loc)
            ))
            # Graphics tiles, 14x14 bytes.
            #locgfx = d['locgfx']
            #converted_tiles, pal = locgfx.convert()
            #data['gfxviews'][loc] = converted_tiles

            #for y in range(14):
            #    f.write("DB ")
            #    for x in range(14):
            #        if x > 0:
            #            f.write(", ")
            #        f.write("{}".format(converted_tiles[(x, y)]))
            #    f.write("\n")
            f.write("DW {} ;; Reference to graphics data\n".format(
                as_graphicsviewlabel(loc)))

            dir_c = len(d['scripts'])
            f.write("DB {}  ; Number of direction script entries here\n".format(dir_c))
            for dir_id in sorted(d['scripts'].keys()):
                for cmd, lbl in sorted(d['scripts'][dir_id].items()):
                    cmd = cmd.lower()
                    f.write("DB {}, {} ; Direction id, command id\n".format(DIRECTION_VALUES[dir_id],
                                                                            PLAYER_COMMANDS[cmd]))
                    f.write("DW {} ; Location of invoked script\n".format(as_scriptlabel(
                        lbl)))
            if "entrancescript" in d:
                f.write("DW {} ; Location of script executed when entering.\n".format(
                    as_scriptlabel(d['entrancescript'])
                ))
            else:
                f.write("DB $ff, $ff; No entry script.\n")


def parse_item(data, cfg, item_key):
    item_d = {'scripts': {}}
    item_name = item_key[len(CFG_ITEM_HEAD):]

    item_d['location'] = cfg.get(item_key, 'location')
    item_sh = cfg[item_key]['name']
    item_d['name'] = item_sh  # item_name
    # item_d['shorthand'] = item_sh

    for k, v in cfg.items(item_key):
        if k.startswith(CFG_SCRIPT_HEAD):
            cmd = k[len(CFG_SCRIPT_HEAD):]
            cmd = PLAYER_COMMANDS[cmd.lower()]
            item_d['scripts'][cmd] = v
    data['items'][item_name] = item_d


def write_item(cfg, data, outfname, outramfname):
    """
    Format:

    DW *item_name
    DW *RAM_record
    DW original_location
    DB commands
    DB command
    DB command1
    DW *command1_script
    ...

    :param outramfname:
    :param cfg:
    :param data:
    :param outfname:
    :return:
    """
    with open(outfname, "w") as f:
        f.write(";;; All item addresses.\n")
        f.write("ITEM_ADDRESS_LIST:\n")
        f.write("  DB {} ;; Number of items\n".format(len(data['items'])))
        f.write("  DW " + ", ".join(
            [as_itemlabel(item) for item in data['items'].keys()]
        ) + "\n")
        f.write(";;; All item init locations.\n")
        f.write("ITEM_INIT_LOCATIONS:\n")
        f.write("  DW " + ", ".join(
            [as_locationlabel(item_d['location']) for item, item_d in data['items'].items()]
        ) + "\n")
        f.write(";;; Item ROM record.\n")
        for item, item_d in data['items'].items():
            f.write("{}:\n".format(as_itemlabel(item)))
            f.write("  DW {} ; Item name\n".format(as_textlabel(item_d['name'])))
            f.write("  DW {} ; RAM address\n".format(as_itemlabel_RAM(item)))
            # f.write("  DW {} ; Original location\n".format(as_locationlabel(item_d['location'])))
            f.write("  DB {} ; Number of commands\n".format(len(item_d['scripts'])))

            for cmd, scr in item_d['scripts'].items():
                f.write("    DB {} \n".format(cmd))
                f.write("    DW {} \n".format(as_scriptlabel(scr)))

    with open(outramfname, 'w') as f:
        f.write(";;; Item RAM data.\n")
        f.write("ITEM_RAM_LOCATIONS:\n")
        for item, item_d in data['items'].items():
            f.write("{}:\n".format(as_itemlabel_RAM(item)))
            f.write("  RW 1 ; Item location\n")


def write_compressed_string(data, f, v, orig):
    c = 0
    cp = huffmanencoder.create_compressed_array(data['huffdict'], v)
    tot_len = len(cp)
    f.write(";; Length: {} vs {}\n".format(len(orig), tot_len))
    while cp:
        b = cp.pop(0)
        if c == 0:
            f.write("\t\tDB {}".format(b))
        else:
            f.write(", {}".format(b))
        c += 1
        if c == 10 or len(cp) == 0:
            f.write("\n")
            c = 0


def merge_colour_codes(all_colours):
    remap = dict((k, k) for k in all_colours)

    # TODO: This doesn't seem to work as desired
    found = True
    # found = False

    print("Reducing used colour codes...")

    reduced = 0
    while found:
        found = False
        for clr1, nclr1 in list(remap.items()):
            for clr2, nclr2 in list(remap.items()):
                if nclr1 == nclr2:
                    continue
                compt, ccode = are_colours_compatible(nclr1, nclr2)
                if compt:
                    # print(nclr1, nclr2, ccode)
                    remap[clr1] = ccode
                    remap[clr2] = ccode
                    found = True
                    reduced += 1
                    break
            else:
                continue
            break

    print("Reduced used colour maps by", reduced, "/", len(all_colours))
    return remap


def are_colours_compatible(colcode1, colcode2):
    ccodes = []
    for c1, c2 in zip(colcode1, colcode2):
        cols1 = set([c1 & 15, (c1 >> 4)])
        cols2 = set([c2 & 15, (c2 >> 4)])
        cm = cols1 | cols2
        cm2 = cm - set([0])
        if len(cm2) > 2:
            return False, []
        c1, c2 = min(cm2), max(cm2)

        ccodes.append((c1 << 4) + c2)
    return True, tuple(ccodes)


def write_tilegfx(cfg, data, fname):
    """
    Write graphics tiles.

    Graphics storage format:
    - 8 bytes for pattern
    - 1 byte to point to correct colour entry; start + point * 8
    """

    with open(fname, 'w') as f:
        f.write(";; Graphics data.\n"
                ";; Each pattern takes 9 bytes; 8 for pattern, 1 for colour table index\n")
        # Create the colour table.
        all_colours = set([])
        defined_chars = data['graphics']['defined_chars']
        for c in defined_chars:
            _, clrs = gfxconvert.split_char(c)
            all_colours.add(clrs)

        colour_remap = merge_colour_codes(all_colours)

        f.write("TILE_COLOUR_TABLE:\n ;; 8 bytes for each distinct colour character.\n")
        all_colours = list(set(colour_remap.values()))

        assert len(all_colours) < 256  # Cannot have more colour patterns now

        for ind, clr in enumerate(all_colours):
            #            f.write(", ".join(["$" + ("00" + hex(v)[2:])[-2:] for v in encoded]) + "\n")

            f.write("    DB " + ", ".join(["$" + ("00" + hex(c)[2:])[-2:] for c in clr]) + " ; {}\n".format(ind))
        f.write("\n")
        f.write("TILE_PATTERN_TABLE:\n ;; tile patterns for each tile.\n")

        chlist = sorted([(v, k) for k, v in defined_chars.items()])
        for ch_ind, ch_pattern in chlist:
            ptrn, clr = gfxconvert.split_char(ch_pattern)
            clr = colour_remap[clr]
            ptrn = gfxconvert.convert_to_palette(ch_pattern, clr)
            f.write(
                "    DB " + ", ".join(intlist_to_string(ptrn)) + ",  " + str(all_colours.index(clr)) + "; {}\n".format(
                    ch_ind))


def write_constants(outfname):
    with open(outfname, 'w') as f:
        f.write(";; Constants from the pregenerator.\n")
        f.write("C_PLAYER_INVENTORY: EQU {}\n".format(CONSTANT_MAP[TC_INVENTORY_LOC]))
        f.write("C_ITEM_LIMBO: EQU {}\n".format(CONSTANT_MAP[TC_LOST_LOC]))
        f.write("C_PLAYER_LOCATION: EQU {}\n".format(CONSTANT_MAP[TC_PLAYER_LOC]))
        f.write("CMD_USE: EQU {}\n".format(PLAYER_COMMANDS['use']))


def produce_data(cfgfile):
    """Main entrypoint."""

    cfg = ConfigParser()
    cfg.optionxform = str
    cfg.read(cfgfile)


    # 1. Collect all items.

    data = read_input(cfg)

    # 2. Convert the graphics.

    palettefname = cfg['out_files']['palette_output']
    gfxfname = cfg['out_files']["tilegfx_output"]
    textfname = cfg['out_files']["texts_output"]
    directionsfname = cfg['out_files']["directions_output"]
    locationsfname = cfg['out_files']["locations_output"]

    scriptfname = cfg['out_files']['script_output']
    itemfname = cfg['out_files']['items_ROM_output']

    itemramfname = cfg['out_files']['items_RAM_output']
    constantsfname = cfg['out_files']['constants_output']

    commandsfname = cfg['out_files']['commands_output']
    huffdictfname = cfg['out_files']['huffdict_output']

    locationgfxname = cfg['out_files']['gfxview_output']

    prepare_graphics(cfg, data)
    write_palettes(cfg, data, palettefname)
    write_tilegfx(cfg, data, gfxfname)

    # 3. Create the complete Huffdict.

    generate_huffdict(cfg, data, huffdictfname)
    # 4. Create the text archive section.
    write_texts(cfg, data, textfname)
    write_direction_names(data, directionsfname)

    # Create the location file
    write_locations(data, locationsfname)

    write_script(data, data['scripts'], scriptfname)

    write_item(cfg, data, itemfname, itemramfname)

    write_constants(constantsfname)

    write_command_names(data, commandsfname)

    write_graphicsview(cfg, data, locationgfxname)

    print("Codes:")
    print(list(CODE_ALPHA.items()))


def produce_gfx(cfgfile):
    cfg = ConfigParser()
    cfg.optionxform = str
    cfg.read(cfgfile)

    produce_regular_gfx.convert_font(
        cfg.get('in_files', 'font'), cfg.get('out_files', 'font')
    )
    produce_regular_gfx.convert_sprite(
        cfg.get('in_files', 'sprites'), cfg.get('out_files', 'sprites')
    )
    produce_regular_gfx.convert_titlescreen(
        cfg.get('in_files', 'title'), cfg.get('out_files', 'title_base')
    )
    produce_regular_gfx.convert_gamescreen(
        cfg.get('in_files', 'ui_view'), cfg.get('out_files', 'ui_view_base')
    )






if __name__ == "__main__":
    # produce_data(os.path.join("content", "samplecontent.cfg"))

    cfgname = os.path.join("..", "resources", "penguingamecontent.cfg")

    produce_gfx(cfgname)

    produce_data(cfgname)


