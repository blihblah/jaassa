import os
from collections import OrderedDict, defaultdict
from itertools import combinations, product

import gfxconvert
import huffmanencoder
import produce_regular_gfx
from io import StringIO


"""
TODO:
- sort gfx tiles by total frequency, then compress them
- "stable" code for items (to avoid RAM storing, point location to starting 
  location
- !!!! CREATE ITEM RAM ADDRESSES FOR ALL ITEMS AT THE SAME TIME!

----
- how to handle the multiple pages:
- place all items and scripts on ONE PAGE now.
- have the scripts produce ALL PAGES of one type in one file.
- labels __TXT_{} etc. will be as before, but the references will be
  __refTXT_{} and defined with EQU ... somehow.
- locations and gfx will be on same pages.
- add "static" toggle to objects that cannot move. Their "RAM" location should
  be in ROM area.

----

- page reference is an EXTRA BYTE:
  - locations
  - scripts
  - items
  - texts
  
- collect all pregen ASM into independent segments
  - then put in the first page the absolutely necessary ones
    - item data
  - then place big ones (optimized location bundles)
  - fill in the gaps with strings, scripts.


- huffdict is constant
- locations are spread out
- gfx are spread
  - locations refer to palette
  - palette refers to page + colour table


"""

from configparser import ConfigParser

CODE_NEWLINE = 2
CODE_UPPERCASE = 1
CODE_TERMINATOR = 0

CODE_ALPHA = dict((c, ord(c) - ord('a') + 3)
                  for c in "abcdefghijklmnopqrstuvwxyz")
#CODE_ALPHA.update(dict((c, ord(c) - ord('A') + 3)
#                       for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
CODE_ALPHA.update(dict((c, ord(c) - ord('A') + 3 + len(CODE_ALPHA))
                       for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
CODE_ALPHA.update(dict((c, len(CODE_ALPHA) + i + 3)
                       for i, c in enumerate(" 0123456789;:.,-!?'\"")))

LABELTEMPLATE_TEXT = "__TXT_{}"
LABELTEMPLATE_ITEM = "__ITEM_{}"
LABELTEMPLATE_LOCATION = "__LOCATION_{}"
LABELTEMPLATE_SCRIPT = "__S_{}"
LABELTEMPLATE_PALETTE = "__PALETTE_{}"
LABELTEMPLATE_ITEM_RAM = "__ITEMRAM_{}"
LABELTEMPLATE_GRAPHICSVIEW = "__GFXVIEW_{}"

REFTEMPLATE_TEXT = "__refTXT_{}"
REFTEMPLATE_ITEM = "__refITEM_{}"
REFTEMPLATE_LOCATION = "__refLOCATION_{}"
REFTEMPLATE_SCRIPT = "__refS_{}"
REFTEMPLATE_PALETTE = "__refPALETTE_{}"
REFTEMPLATE_ITEM_RAM = "__refITEMRAM_{}"
REFTEMPLATE_GRAPHICSVIEW = "__refGFXVIEW_{}"

REFEQU_TEMPLATE = "{}: equ (({} << 14) + ({} AND $3FFF))\n"

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

PAGE_MAX_SIZE = 2 ** 14 - 22

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
    "WAITFORFIRE": 15,
    "JUMP": 16,
    "ISSTATELEQ": 17,
    "TO_MAIN_MENU": 18,
    "PLAYSOUND": 19
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
    "wear": 12,
    "remove": 13,
    "choose": 14,
    "pull": 15,
    "connect": 16,
    "unscrew": 17,
    "open": 18,
    "close": 19,
    "get on": 20,
    "push": 21

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


def encode_text(s, is_prewrapped=False):
    """
    Convert a string to a sequence of characters
    to pack.
    """
    if not is_prewrapped:
        s = wordwrap_text(s)
    res = []
    for c in s:
        if c == "\\":
            res.append(CODE_NEWLINE)
            continue
        #elif c.upper() == c and c.lower() != c:
        #    res.append(CODE_UPPERCASE)
        res.append(CODE_ALPHA[c])
    if len(res) == 0:
        res.append(CODE_ALPHA[' '])
    res.append(CODE_TERMINATOR)
    return bytes(res)

def write_chapterheader(cfg, data, fname):
    """
    Write the chapter header for this chapter.
    """
    startloc = cfg['general']['starting_location']

    key_suffix = "_" + cfg['general']['chapter_suffix']

    with open(fname, 'w') as f:
        f.write(";; Chapter header\n")
        f.write("EPISODEHEADERSTART:\n")
        f.write("DB {} ;; Chapter start location\n".format(
            as_page_location(startloc)
        ))
        f.write("DW {} ;; Chapter start location\n".format(
            as_locationlabel(startloc)))

        f.write("DB 2 ;; \n")
        f.write("DW ITEM_ADDRESS_LIST_BIG ;; Item address list\n")

        f.write("DB 2 ;; \n".format(
            as_page_location(startloc)
        ))
        f.write("DW ITEM_INIT_LOCATIONS_BIG ;; Item init locations\n".format(
            as_locationlabel(startloc)))
        f.write("DB C_ITEM_PAGE ;; Which page has the item definitions.\n")


def write_direction_names(cfg, data, fname):
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
            encs, _ = create_compressed_string(data, enc, v)
            #write_compressed_string(data, f, enc, v)
            f.write(encs)
        f.write("DIRECTION_NAMES:\n")
        f.write("DW {}\n".format(", ".join(dnames)))

        f.write(";; Constant strings\n")
        for k in ("SelectObject", "SelectVerb", "SelectTarget"):
            v_orig = cfg['text'][k]
            v = encode_text(v_orig, is_prewrapped=(k in data['prewrapped_texts']))
            f.write("{}: ;;\n".format(LABELTEMPLATE_TEXT.format(k)))
            #write_compressed_string(data, f, v, v_orig)
            f.write(
                create_compressed_string(data, v, v_orig)[0]
            )


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
            f.write(create_compressed_string(data, enc, v)[0])
            #write_compressed_string(data, f, enc, v)
        f.write("COMMAND_NAMES:\n")
        f.write("DW {}\n".format(", ".join(dnames)))

def create_text_elements(cfg, data):
    """
    Writes the items under [text] section.
    """
    d = cfg['text']
    results = []
    for k, v_orig in d.items():
        if k in ["SelectTarget", "SelectVerb", "SelectObject"]:
            continue
        v = encode_text(v_orig, is_prewrapped=(k in data['prewrapped_texts']))

        encoded, length = create_compressed_string(data, v, v_orig)
        encoded = f"{as_textlabel(k)}:\n" + encoded
        encoded += f";; My size: {length}\n"

        results.append(WritableElement("text", length, encoded,
                                       as_page_textlabel(k)))
    return results

def generate_huffdict(cfg, data, out_fname, all_texts):
    """
    Generate the huffdict from the strings in all_inputs.
    """

    #all_inputs = extract_displayed_strings(cfg, data)
    all_inputs = all_texts.values()
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

def longtext(cfg, data, s_name, text):
    """
    Split a long text paragraph into distinct pieces.
    Return the distinct strings.
    """
    if text is None:
        # Was missing from input.
        data['used_strings'].add(s_name)
        return [s_name]
    text = wordwrap_text(text)
    LINES = 6
    entries = []
    SUB_LEN = LINES * LINE_LENGTH
    while len(text) > SUB_LEN:
        entries.append(text[:SUB_LEN].strip())
        text = text[SUB_LEN:]
    if len(text) > 0:
        entries.append(text.strip())

    n_names = []
    for i, v in enumerate(entries):
        n_name = f"{s_name}_PT{i}"
        data['used_strings'].add(n_name)
        n_names.append(n_name)
        cfg['text'][n_name] = v
        data['prewrapped_texts'].add(n_name)
    del cfg['text'][s_name]
    return n_names



def parse_scriptfile(cfg, data, infilename):
    scripts = {}
    current_script = None
    valid_ends = [COMMAND_MAP[s] for s in ("END", "GOEND", "TEXTEND", "TAKEEND",
                                           "LOCATIONTEXTEND", "JUMP",
                                           "TO_MAIN_MENU")]
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
                data['used_locations'].add(parts[1])
            elif cmd == "SETITEMLOC":
                current_script.append((cmdval, parts[1], parts[2]))
                data['used_locations'].add(parts[2])
            elif cmd == "TEXT":
                current_script.append((cmdval, parts[1]))
                data['used_strings'].add(parts[1])
            elif cmd == "IFTRUE":
                # parts[1] should be a script name
                current_script.append((cmdval, parts[1]))
                data['used_scripts'].add(parts[1])
            elif cmd == "SET":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "ISLOC":
                current_script.append((cmdval, parts[1]))
                data['used_locations'].add(parts[1])
            elif cmd == "ISSTATE":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "SETTILE":
                current_script.append((cmdval, parts[1], parts[2], parts[3]))
            elif cmd == "GOEND":
                current_script.append((cmdval, parts[1]))
                data['used_locations'].add(parts[1])
            elif cmd == "TEXTEND":
                current_script.append((cmdval, parts[1]))
                data['used_strings'].add(parts[1])
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
            elif cmd == "JUMP":
                current_script.append((cmdval, parts[1]))
            elif cmd == "ISSTATELEQ":
                current_script.append((cmdval, parts[1], parts[2]))
            elif cmd == "TO_MAIN_MENU":
                current_script.append((cmdval,))
            elif cmd == "LONGTEXT":
                txtcmd = COMMAND_MAP["TEXT"]
                waitcmd = COMMAND_MAP["WAITFORFIRE"]
                entries = longtext(cfg, data, parts[1], cfg['text'].get(parts[1], None))
                for entry in entries:
                    current_script.append((txtcmd, entry))
                    if entry is not entries[-1]:
                        current_script.append((waitcmd,))
            elif cmd == "PLAYSOUND":
                current_script.append((cmdval, parts[1]))
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


def create_script_elements(data, script_commands):
    """
    Write the script commands in the parameter.
    :param outfn:
    :param data:
    :param script_commands:
    """
    results = []
    for script, cmds in script_commands.items():
        f = StringIO()
        script_length = 0
        f.write("  {}: ;; Script {}\n".format(
            as_scriptlabel(script), script))
        for cmd in cmds:
            script_length += 1
            f.write("  DB {}\n".format(cmd[0]))
            if cmd[0] == 0:  # END
                pass
            elif cmd[0] == 1:  # GOTO
                f.write("    DB {}\n".format(as_page_location(cmd[1])))
                f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 2:  # SETITEMLOC
                f.write("    DB {}\n".format(as_page_itemlabel(cmd[1])))
                f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                f.write("    DB {}\n".format(as_page_location(cmd[2])))
                f.write("    DW {}\n".format(as_locationlabel(cmd[2])))
                script_length += 6
            elif cmd[0] == 3:  # TEXT
                f.write("    DB {}\n".format(as_page_textlabel(cmd[1])))
                f.write("    DW {}\n".format(as_textlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 4:  # IFTRUE
                f.write("    DB {}\n".format(as_page_scriptlabel(cmd[1])))
                f.write("    DW {}\n".format(as_scriptlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 5:  # SET
                f.write("    DB {}\n    DB {}\n".format(
                    cmd[1], cmd[2]
                ))
                script_length += 2
            elif cmd[0] == 6:  # ISLOC
                f.write("    DB {}\n".format(as_page_location(cmd[1])))
                f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 7:  # ISSTATE
                f.write("    DB {}, {}\n".format(cmd[1], cmd[2]))
                script_length += 2
            elif cmd[0] == 8:  # SETTILE
                f.write("    DB {}, {}, {}, {}\n".format(*cmd[1:5]))
                script_length += 4
            elif cmd[0] == 9:  # GOEND
                f.write("    DB {}\n".format(as_page_location(cmd[1])))
                f.write("    DW {}\n".format(as_locationlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 10:  # TEXTEND
                f.write("    DB {}\n".format(as_page_textlabel(cmd[1])))
                f.write("    DW {}\n".format(as_textlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 11:  # TAKE
                f.write("    DB {}\n".format(as_page_itemlabel(cmd[1])))
                f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 12:  # TAKEEND
                f.write("    DB {}\n".format(as_page_itemlabel(cmd[1])))
                f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 13:  # ISOBJECT
                if cmd[1] in data['items']:
                    f.write("    DB {}\n".format('C_ITEM_INVENTORY_ICON'))
                    f.write("    DB {}\n".format(as_page_itemlabel(cmd[1])))
                    f.write("    DW {}\n".format(as_itemlabel(cmd[1])))
                    script_length += 4
                else:
                    d_ind = DIRECTION_VALUES[cmd[1].lower()]
                    f.write("    DB {}, {}, 0\n".format(
                        'C_ITEM_DIRECTION', d_ind))
                    script_length += 3
            elif cmd[0] == 17:  # ISSTATELEQ
                f.write("    DB {}, {}\n".format(cmd[1], cmd[2]))
                script_length += 2
            elif cmd[0] == 16:  # JUMP
                f.write("    DB {}\n".format(as_page_scriptlabel(cmd[1])))
                f.write("    DW {}\n".format(as_scriptlabel(cmd[1])))
                script_length += 3
            elif cmd[0] == 19:  # PLAYSOUND
                f.write("    DW {}\n".format(cmd[1]))
                script_length += 2
        f.write(f";; My size {script_length}\n")

        results.append(WritableElement("script", script_length, f.getvalue(),
                                       as_page_scriptlabel(script)))
    return results


def read_input(cfg):
    data_collection = {
        'locations': OrderedDict(),
        'items': OrderedDict(),
        'graphics': {
            'defined_chars': {}
        },
        'used_strings': set([]),
        'used_locations': set([]),
        'used_scripts': set([]),
        'prewrapped_texts': set([]),
        'scripts': {},
        'gfxviews': {},
        'gfxsources': {},
        'errors': {
            'strings': [],
            'scripts': [],
            'gfx': [],
            'locations': []
        }
    }
    #print("Reading input")
    for s in cfg.sections():
        if s.startswith(CFG_LOCATION_HEAD):
            parse_location(data_collection, cfg, s)
        elif s.startswith(CFG_ITEM_HEAD):
            parse_item(data_collection, cfg, s)
    parse_scriptfile(cfg, data_collection, cfg['in_files']['scripts'])
    return data_collection


def as_textlabel(s):
    return LABELTEMPLATE_TEXT.format(s)

def as_page_textlabel(s):
    return f"page{as_textlabel(s)}"

def db_textlabel(s):
    return (f"    DB {as_page_textlabel(s)}\n" +
            f"    DW {as_textlabel(s)}\n")

def as_page_tilegfx(s):
    return f"page{as_tilegfxlabel(s)}"

def as_tilegfxlabel(s):
    return f"__TILEGFX_{s}"

def as_page_tilecolourlabel(s):
    return f"page{as_tilecolourlabel(s)}"

def as_tilecolourlabel(s):
    return f"__TILECLR_{s}"


def as_scriptlabel(s):
    return LABELTEMPLATE_SCRIPT.format(s)

def as_page_scriptlabel(s):
    return f"page{as_scriptlabel(s)}"

def db_scriptlabel(s):
    return (f"    DB {as_page_scriptlabel(s)}\n" +
            f"    DW {as_scriptlabel(s)}\n")


def as_itemlabel(s):
    return LABELTEMPLATE_ITEM.format(s)

def as_page_itemlabel(s):
    return f"page{as_itemlabel(s)}"

def db_itemlabel(s):
    return (f"    DB {as_page_itemlabel(s)}\n" +
            f"    DW {as_itemlabel(s)}\n")

def as_itemlabel_RAM(s):
    return LABELTEMPLATE_ITEM_RAM.format(s)


def as_locationlabel(s):
    if s not in CONSTANT_MAP:
        return LABELTEMPLATE_LOCATION.format(s)
    else:
        return CONSTANT_MAP[s]


def as_page_location(s):
    if s in CONSTANT_MAP.keys():
        return "0"
    print(repr(s))

    return f"page{as_locationlabel(s)}"

def db_locationlabel(s):
    return (f"    DB {as_page_location(s)}\n" +
            f"    DW {as_locationlabel(s)}\n")


def as_palettelabel(s):
    return LABELTEMPLATE_PALETTE.format(s)

def as_page_palettelabel(s):
    return f"page{as_palettelabel(s)}"



def as_graphicsviewlabel(s):
    return LABELTEMPLATE_GRAPHICSVIEW.format(s)

def as_page_graphicsview(s):
    return f"page{as_graphicsviewlabel(s)}"


def as_page_tilegfxtiles(s):
    return f"page{as_tilegfxtiles(s)}"

def as_tilegfxtiles(s):
    return f"__TILEGFX_{s}"


def intlist_to_string(s):
    return [str(i) for i in s]


def parse_location(data, cfg, loc_key):
    loc_name = loc_key[len(CFG_LOCATION_HEAD):]
    gfx_file = cfg.get(loc_key, 'gfx')
    defined_chars = data['graphics']['defined_chars']
    if not os.path.exists(gfx_file):
        data['errors']['gfx'].append(gfx_file)
        return

    if gfx_file not in data['gfxsources']:
        data['gfxsources'][gfx_file] = {
            'palette': loc_name,
            'gfxdata': loc_name,
            'loc_name': loc_name
        }

    defined_chars, tiles = gfxconvert.create_charset(gfx_file, defined_chars)
    #print("Created tiles.")
    loc = {'scripts': {},
           'palette': data['gfxsources'][gfx_file]['palette'],
           'gfxdata': data['gfxsources'][gfx_file]['gfxdata']}
    data['locations'][loc_name] = loc
    #loc['gfx'] = tiles
    if 'gfx' not in data['gfxsources'][gfx_file]:
        data['gfxsources'][gfx_file]['gfx'] = tiles
    text_key = cfg.get(loc_key, 'description')
    data['used_strings'].add(text_key)
    loc['description'] = text_key
    for k in cfg[loc_key]:
        if k.startswith(CFG_SCRIPT_HEAD):
            rest = k[len(CFG_SCRIPT_HEAD):]
            dname, cmd = rest.split("_")
            for d in DIRECTION_VALUES:
                if dname.lower() == d.lower():

                    if d not in loc['scripts']:
                        loc['scripts'][d] = {}
                    loc['scripts'][d][cmd] = cfg[loc_key][k]
                    data['used_scripts'].add(cfg[loc_key][k])
    if "entrancescript" in cfg[loc_key]:
        loc['entrancescript'] = cfg.get(loc_key, "entrancescript")
        data['used_scripts'].add(cfg.get(loc_key, "entrancescript"))
    else:
        defscript = cfg.get("general", "default_entry_script")
        loc['entrancescript'] = defscript #"DefaultEntryScript"
        data['used_scripts'].add(defscript)


def prepare_graphics(cfg, data):
    """
    Prepare the graphics tiles to a binary.
    """
    for gfxfile, loc_d in data['gfxsources'].items():

        # Create a list of all tiles we're using in this feature.
        # Then create a palette.
        used_orig_tiles = loc_d['gfx']

        locgfx = LocationGraphics()
        locgfx.original_tiles = used_orig_tiles
        loc_d['locgfx'] = locgfx
        loc_name = loc_d['loc_name']
        data['gfxviews'][loc_name] = locgfx


def create_palette_elements(cfg, data):
    res_elems = []
    return res_elems

    # TODO: COLOUR TABLES
    for loc_file, loc_d in data['gfxsources'].items():
        f = StringIO()
        f.write(";; Palettes for locations.\n")
        length = 0
        loc_name = loc_d['loc_name']
        locgfx = loc_d['locgfx']
        ctvd, palette = locgfx.convert()
        f.write("{}:\nDB ".format(as_palettelabel(loc_name)))
        encoded = palette.encode()
        length += len(encoded)
        f.write(", ".join(
            ["$" + ("00" + hex(v)[2:])[-2:] for v in encoded]) + "\n")
        f.write(f";; My size {length}\n")
        res_elems.append(WritableElement('palette', length, f.getvalue(),
                            as_page_palettelabel(loc_name)))
    return res_elems


def create_graphicsview_elements(cfg, data):
    """
    TODO: Split the locations, palettes, graphics and colours into separate
    pages BEFORE calling this!
    """
    elements = []
    return elements
    for gfx_name, gfx_d in data['gfxviews'].items():
        f = StringIO()
        size = 0
        ctvd, palette = gfx_d.convert()
        f.write("{}:\n".format(as_graphicsviewlabel(gfx_name)))
        for y in range(14):
            f.write("DB ")
            for x in range(14):
                if x > 0:
                    f.write(", ")
                f.write("{}".format(ctvd[(x, y)]))
                size += 1
            f.write("\n")
        f.write(f";; My size: {size}\n")
        elements.append(WritableElement("gfxview", size, f.getvalue(),
                                        as_page_graphicsview(gfx_name)))
    return elements


class WritableElement(object):
    def __init__(self, etype, length, text, pagelabel):
        self.length = length
        self.etype = etype
        self.text = text
        self.pagelabel = pagelabel



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

    def remap(self, remapping):
        t2p = {}
        p2t = {}


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

    def rebase(self, remap):
        self.palette = None
        self.original_tiles = dict((k, remap[v])
                                   for k, v in self.original_tiles.items())


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
                converted[(x, y)] = palette.tile2palette[
                    self.original_tiles[(x, y)]]
        return converted, palette



def create_location_elements(data):
    """
    ;; Location records: 10 + 14*14 + 1 + 3*3 = 216
    ;; [description, compressed]
    ;; [gfx tiles, fixed size]
    ;; [how many directions [byte]]
    ;; [direction_code][script pointer] * num_of_directions
    ;; [commands to alter the looks]
    """
    elements = []

    for loc, d in data['locations'].items():
        f = StringIO()
        size = 0
        f.write("{}:\n".format(as_locationlabel(loc)))
        # Now, link to description.
        f.write("DB {} \n".format(as_page_textlabel(d['description'])))
        f.write("DW {}  ;; Location description\n".format(
            as_textlabel(d['description'])))
        size += 3
        # Which tileset to use (3 bytes)
        f.write("DB {} ;; Page\n".format(
            as_page_tilegfxtiles(d['tile_graphics_set_page']))
        )
        f.write("DW {} ;; Start of tile graphics definitions\n".format(
            as_tilegfxtiles(d['tile_graphics_set'])
        ))
        size += 3
        # tiles + gfx are always on the same page
        f.write(";; Start of tile palette definitions\nDW {}\n".format(
            as_tilecolourlabel(d['tile_colours_set'])
        ))
        size += 2

        # Which tile dictionary to use (2 bytes)
        #f.write("DB {}\n".format(as_page_palettelabel(d['palette'])))
        f.write("DW {} ;; Start of tile dictionary location\n".format(
            as_palettelabel(d['palette'])
        ))
        size += 2
        #f.write("DB {}\n".format(as_page_graphicsview(d['gfxdata'])))
        f.write("DW {} ;; Reference to graphics data\n".format(
            as_graphicsviewlabel(d['gfxdata'])))
        size += 2

        dir_c = sum(len(d['scripts'][k]) for k in d['scripts'])
        f.write("DB {}  ; Number of direction script entries here\n"
                .format(dir_c))
        size += 1
        for dir_id in sorted(d['scripts'].keys()):
            for cmd, lbl in sorted(d['scripts'][dir_id].items()):
                cmd = cmd.lower()
                f.write("DB {}, {} ; Direction id, command id\n"
                        .format(DIRECTION_VALUES[dir_id],
                                PLAYER_COMMANDS[cmd]))
                f.write("DB {}\n".format(as_page_scriptlabel(lbl)))
                f.write("DW {} ; Location of invoked script\n"
                        .format(as_scriptlabel(lbl)))
                data['used_scripts'].add(lbl)
                size += 5
        if "entrancescript" in d:
            f.write("DB {}\n".format(as_page_scriptlabel(d['entrancescript'])))
            f.write("DW {} ; Location of script executed when entering.\n"
                    .format(as_scriptlabel(d['entrancescript'])))
            data['used_scripts'].add(d['entrancescript'])
        else:
            f.write("DB $ff, $ff, $ff; No entry script.\n")
        size += 3
        f.write(f";; My size: {size}\n")
        elements.append(WritableElement("location", size, f.getvalue(),
                                        as_page_location(loc)))
    return elements


def parse_item(data, cfg, item_key):
    item_d = {'scripts': {}}
    item_name = item_key[len(CFG_ITEM_HEAD):]

    item_d['location'] = cfg.get(item_key, 'location')
    data['used_locations'].add(item_d['location'])

    item_sh = cfg[item_key]['name']
    item_d['name'] = item_sh  # item_name
    # item_d['shorthand'] = item_sh

    for k, v in cfg.items(item_key):
        if k.startswith(CFG_SCRIPT_HEAD):
            cmd = k[len(CFG_SCRIPT_HEAD):]
            cmd = PLAYER_COMMANDS[cmd.lower()]
            item_d['scripts'][cmd] = v

    # Flags
    item_d['static'] = cfg.has_option(item_key, 'static')
    data['items'][item_name] = item_d


def create_item_elements(cfg, data, max_itemcount):
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

    size = 0

    item_base_stats = StringIO()
    #chapter_suffix = cfg['general']['chapter_suffix']
    chapter_suffix = "BIG"

    item_base_stats.write(";;; All item addresses.\n")
    item_base_stats.write("ITEM_ADDRESS_LIST_{}:\n".format(chapter_suffix))
    item_base_stats.write("  DB {} ;; Number of items\n".format(len(data['items'])))
    size += 1

    for item in sorted(data['items'].keys()):
        item_base_stats.write("DB {} ;; Item address\n".format(
            as_page_itemlabel(item)))
        item_base_stats.write("DW {} ;; \n".format(as_itemlabel(item)))
        size += 3

    #item_base_stats.write("  DW " + ", ".join(
    #        [as_itemlabel(item) for item in sorted(data['items'].keys())]
    #) + "\n")
    size += 1 + len(data['items']) * 2
    item_base_stats.write(";;; All item init locations.\n")
    item_base_stats.write("ITEM_INIT_LOCATIONS_{}:\n".format(chapter_suffix))
    for item, item_d in sorted(data['items'].items()):
        item_base_stats.write("  DB {} ;; Location page WHY?!\n".format(
            as_page_location(item_d['location'])
        ))
        item_base_stats.write("  DW {} ;; Location on page\n".format(
            as_locationlabel(item_d['location'])
        ))
        size += 3
    item_base_stats.write(f";; My size: {size}\n")

    # What was this used for, again?
    #item_base_stats.write("  DW " + ", ".join(
    #        [as_locationlabel(item_d['location'])
    #         for item, item_d in sorted(data['items'].items())]
    #) + "\n")
    #size += 1 + len(data['items']) * 2



    # We're writing ALL of this item stuff on one page.

    item_records = []

    for item, item_d in sorted(data['items'].items()):
        f = StringIO()
        record_size = 0
        f.write("{}:\n".format(as_itemlabel(item)))
        f.write("  DB {} ; Item name page\n"
                .format(as_page_textlabel(item_d['name'])))
        f.write("  DW {} ; Item name\n"
                .format(as_textlabel(item_d['name'])))
        f.write("  DW {} ; RAM address\n"
                .format(as_itemlabel_RAM(item)))
        f.write("  DB {} ; Number of commands\n"
                .format(len(item_d['scripts'])))
        record_size += 6

        for cmd, scr in item_d['scripts'].items():
            f.write("    DB {} \n".format(cmd))
            f.write("    DB {} \n".format(as_page_scriptlabel(scr)))
            f.write("    DW {} \n".format(as_scriptlabel(scr)))
            data['used_scripts'].add(scr)
            record_size += 4

        data['used_strings'].add(item_d['name'])
        f.write(f";; My size: {record_size}\n")
        item_records.append(
            WritableElement("item", record_size, f.getvalue(), as_page_itemlabel(item))
        )


    items = len(data['items'])
    while items < max_itemcount:
        items += 1
        item_base_stats.write("  DB 0, 0, 0 ; Item name slot\n"
                .format(as_textlabel(item_d['name'])))
        item_base_stats.write("  DW 0 ; RAM address slot\n"
                .format(as_itemlabel_RAM(item)))
        item_base_stats.write("  DB 0 ; Number of commands\n"
                .format(len(item_d['scripts'])))
        size += 3 + 2 + 1


    return ([WritableElement("items", size, item_base_stats.getvalue(), "C_ITEMPAGE")],
            item_records)


def write_all_item_ram_addresses(outramfname, cfgs, maxitems):
    with open(outramfname, 'w') as f:
        f.write(";;; Item RAM data.\n")
        f.write("ITEM_RAM_LOCATIONS:\n")
        #for item, item_d in data['items'].items():
        #    f.write("{}:\n".format(as_itemlabel_RAM(item)))
        #    f.write("  RW 1 ; Item location\n")
        f.write(f"  RB {3*maxitems}\n")
        for cfg in cfgs:
            ind_counter = 0
            for k in sorted(cfg.keys()):
                if k.lower().startswith("item_"):
                    f.write("  {}: EQU ITEM_RAM_LOCATIONS + {}\n".format(
                        as_itemlabel_RAM(k[5:]), 3 * ind_counter
                    ))
                    ind_counter += 1


def create_compressed_string(data, v, orig):
    c = 0
    result = []
    cp = huffmanencoder.create_compressed_array(data['huffdict'], v)
    tot_len = len(cp)
    result.append(";; Length: {} vs {}\n".format(len(orig), tot_len))
    while cp:
        b = cp.pop(0)
        if c == 0:
            result.append("\t\tDB {}".format(b))
        else:
            result.append(", {}".format(b))
        c += 1
        if c == 10 or len(cp) == 0:
            result.append("\n")
            c = 0
    return "".join(result), tot_len


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
                    remap[clr1] = ccode
                    remap[clr2] = ccode
                    found = True
                    reduced += 1
                    break
            else:
                continue
            break

    print("Reduced used colour maps by", reduced, "/", len(all_colours))
    print("Colours altogether:", len(set(remap.values())))
    return remap

def merge_colour_codes_alt2(all_colours):
    """
    An alternative heuristic for merging colour codes.
    Find the tiles with most palette-compatible tiles, then try finding the
    largest set of palette-compatible tiles from these. Repeat until no palettes
    are compatible.
    :param all_colours:
    :return:
    """
    remap = dict((k, k) for k in all_colours)

    found = True

    while found:
        found = False
        # 1. Find all pairwise compatibles.
        # 2. Find ones with most shared

        compatible = defaultdict(list)
        for nclr1, nclr2 in product(set(remap.values()), repeat=2):
            if nclr1 == nclr2:
                continue
            compt, ccode = are_colours_compatible(nclr1, nclr2)
            if compt:
                compatible[nclr1].append(nclr2)
        options = list((len(v), k, v) for k, v in compatible.items())
        options.sort(reverse=True)
        if len(options):
            found = True
            nbs, clr0, choice = options[0]

            compatibles = [
                ([clr0], clr0)
            ]
            for i, clr1 in enumerate(choice):
                to_add = []
                for others, clr2 in compatibles:
                    compt, ccode = are_colours_compatible(clr1, clr2)
                    if compt:
                        to_add.append(
                            (others + [clr1], ccode)
                        )
                compatibles.extend(to_add)
                MAX_EVALS = 500
                if len(compatibles) > MAX_EVALS:
                    opts = [(len(k), k, v) for k, v in compatibles]
                    opts.sort(reverse=True)
                    compatibles = [(k[1], k[2]) for k in opts[:MAX_EVALS]]

            opts = [(len(k), v, k) for k, v in compatibles]
            opts.sort(reverse=True)
            best = opts[0][2]
            ccode = opts[0][1]
            for clr in best:
                remap[clr] = ccode

    print("    Colour schemes used", len(set(remap.values())), ", originally", len(all_colours))
    return remap

def are_colours_compatible(colcode1, colcode2, debug=False):
    ccodes = []
    for c1, c2 in zip(colcode1, colcode2):
        cols1 = set([c1 & 15, (c1 >> 4)])
        cols2 = set([c2 & 15, (c2 >> 4)])
        if debug:
            print(c1, cols1, c2, cols2)
        cm = cols1 | cols2
        cm2 = cm - set([0])
        if len(cm2) > 2:
            if debug:
                print("Not compatible")
            return False, []
        c1, c2 = min(cm2), max(cm2)

        ccodes.append((c1 << 4) + c2)
        if debug:
            print("Added", ccodes[-1])
    if debug:
        print("Was compatible.")
    return True, tuple(ccodes)

def split_tilegfx(cfg, data):
    """
    Each location has tilemap + gfx. If locations are limited to same page:
    - find all locations w/ most shared tiles
    - create an overestimate of how many bytes the data would take.
      - it's OK to understuff a page, not OK to overstuff it.

    - start with each location as a singular bundle
    - estimate the size of all pairs of location bundles
    - merge the best pair that can be merged without exceeding the page size
    - repeat

    """

    # 1. Create singular bundles.
    bundles = []
    def_tiles = data['graphics']['defined_chars']
    inverted_defined = dict((v, k) for k, v in def_tiles.items())

    def used_tiles(gfxnames):
        together = set([])
        for fn in gfxnames:
            together.update(set(data['gfxsources'][fn]['gfx'].values()))
        return together

    def merge_tile_colours(tiles):
        gfxtiles = set(inverted_defined[ch] for ch in tiles)
        all_colours = set([])
        for c in gfxtiles:
            _, clrs = gfxconvert.split_char(c)
            all_colours.add(clrs)
        colours_used = merge_colour_codes_alt2(all_colours)
        return colours_used


    print("Pregenerating...")
    for gfxfile, loc_d in data['gfxsources'].items():
        #used_orig_tiles = set(loc_d['gfx'].values())
        tiles = used_tiles([gfxfile])
        # 8 bytes for pattern + 1 for colour scheme
        size = len(tiles) * 9
        colours_used = merge_tile_colours(tiles)
        size += len(set(colours_used.values())) * 8
        size += (14 * 14 + 14 * 14 * 2)
        print(gfxfile, size)
        bundles.append(
            ([gfxfile], size, tiles, colours_used)
        )


    max_loops = 4
    quick = False
    if not quick:

        found = True
        by_tiles = {}
        while found and max_loops > 0:
            found = False
            # Estimate the size of all pairs of location bundles
            pairwise_sizes = []

            print("Total size currently used:",
                  sum(p[1] for p in bundles), "bundles:", len(bundles))

            for p1, p2 in combinations(bundles, 2):
                tiles = p1[2] | p2[2]
                key = frozenset(tiles)
                if key not in by_tiles:
                    colours_used = merge_tile_colours(tiles)
                    by_tiles[key] = colours_used
                colours_used = by_tiles[key]
                diff_clrs = len(set(colours_used.values()))
                size = 8 * diff_clrs + 9 * len(tiles)

                # 14 *14 * 2 = overestimate of palette length.
                size += (14*14 + 14 * 14 * 2) * len(p1[0] + p2[0])

                if diff_clrs > 254:
                    # Exceeds size limits, cannot merge.
                    continue
                if size > 16000:
                    # Exceeds page size (with safety margin)
                    continue
                if size - (p1[1] + p2[1]) == 0:
                    print("Ignoring a solution that wouldn't improve")
                    continue
                pairwise_sizes.append(
                    (float(size) - (p1[1] + p2[1]), size, (p1, p2),
                     tiles, colours_used)
                )
            if len(pairwise_sizes) > 0:
                found = True
                best = min(pairwise_sizes)
                print("Merging to save", -best[0], "bytes with max size",
                      best[1])
                print(best[2][0][0], best[2][1][0])
                size, parts = best[1], best[2]
                bundles = [k for k in bundles if
                           k not in parts]
                bundles.append(
                    (parts[0][0] + parts[1][0], size, best[3], best[4])
                )

        print("Done merging.")
    else:
        print("Skipping the space-saving merge step.")

    data['gfxbundles'] = {}
    for ind, b in enumerate(bundles):
        bname = f"tileblock_{ind}"
        renumerated = dict(
            (k, i) for i, k in enumerate(sorted(b[2]))
        )
        defined = dict(
            (inverted_defined[i], renumerated[i]) for i in b[2]
        )

        # Now, we need to RESET THE LOCATION GRAPHICS


        data['gfxbundles'][bname] = {
            'colours': b[3],
            'tile_remap': renumerated,
            'defined_chars': defined
        }
        # TODO: Redo the palettes?

        for c in b[0]:
            data['gfxsources'][c]['bundle'] = bname
            data['gfxsources'][c]['locgfx'].rebase(renumerated)

            for loc in data['locations'].values():
                if loc['gfxdata'] == data['gfxsources'][c]['gfxdata']:
                    loc['tile_graphics_set'] = bname
                    loc['tile_colours_set'] = bname
                    loc['tile_graphics_set_page'] = bname


        #data['gfxsources'][gfx_file]['gfxdata']





def create_tilegfx_elements(cfg, data):
    """
    Write graphics tiles.

    Graphics storage format:
    - 8 bytes for pattern
    - 1 byte to point to correct colour entry; start + point * 8
    """

    # TODO: Limit to what is on one page

    result = []
    for bname, bundle in data['gfxbundles'].items():
        size = 0
        f = StringIO()
        f.write(";; Graphics data.\n"
            ";; Each pattern takes 9 bytes; 8 for pattern,\n"
            ";; 1 for colour table index\n")
        # Create the colour table.
        all_defined_chars = data['graphics']['defined_chars']
        colour_remap = bundle['colours']
        tile_remap = bundle['tile_remap']
        defined_chars = bundle['defined_chars']

        #for c in defined_chars:
        #    _, clrs = gfxconvert.split_char(c)

        chapter_suffix = cfg['general']['chapter_suffix']

        #f.write(f"TILE_COLOUR_TABLE_{chapter_suffix}_{bname}:\n"
        #        ";; 8 bytes for each distinct colour character.\n")
        f.write(f"{as_tilecolourlabel(bname)}:\n")
        all_colours = list(set(colour_remap.values()))

        assert len(all_colours) < 256  # Cannot have more colour patterns now

        for ind, clr in enumerate(all_colours):
            f.write("    DB " +
                    ", ".join(["$" + ("00" + hex(c)[2:])[-2:] for c in clr]) +
                    " ; {}\n".format(ind))
            size += len(clr)
        f.write("\n")
        #f.write(f"TILE_PATTERN_TABLE_{chapter_suffix}_{bname}:\n "
        f.write(f"{as_tilegfxtiles(bname)}:\n "
                f";; tile patterns for each tile.\n")

        chlist = sorted([(v, k) for k, v in defined_chars.items()])
        for ch_ind, ch_pattern in chlist:
            ptrn, clr = gfxconvert.split_char(ch_pattern)
            if clr not in colour_remap:
                print(colour_remap)
            clr = colour_remap[clr]
            ptrn = gfxconvert.convert_to_palette(ch_pattern, clr)
            f.write(
                "    DB " + ", ".join(intlist_to_string(ptrn)) + ",  " +
                str(all_colours.index(clr)) + "; {}\n".format(ch_ind))
            size += 9
        f.write(f";; My size: {size}\n")


        # Now, write the palettes.
        for loc_file, loc_d in data['gfxsources'].items():
            if loc_d['bundle'] != bname:
                continue
            loc_name = loc_d['loc_name']
            locgfx = loc_d['locgfx']

            # TODO 2021

            f.write(";; Palettes for locations.\n")
            ctvd, palette = locgfx.convert()
            f.write("{}:\nDB ".format(as_palettelabel(loc_name)))
            encoded = palette.encode()
            size += len(encoded)
            f.write(", ".join(
                ["$" + ("00" + hex(v)[2:])[-2:] for v in encoded]) + "\n")
            f.write(f";; My size {size}\n")
            #res_elems.append(WritableElement('palette', length, f.getvalue(),
            #                                 as_page_palettelabel(loc_name)))

            # dfdsjfkjd


            # THIS IS BAD.

            for gfx_name, gfx_d in data['gfxviews'].items():
                #print("Comparing", gfx_name, loc_name)
                if gfx_name != loc_name:
                    continue

                #f = StringIO()
                #size = 0
                ctvd, palette = gfx_d.convert()
                f.write("{}:\n".format(as_graphicsviewlabel(gfx_name)))
                for y in range(14):
                    f.write("DB ")
                    for x in range(14):
                        if x > 0:
                            f.write(", ")
                        f.write("{}".format(ctvd[(x, y)]))
                        size += 1
                    f.write("\n")
                f.write(f";; My size: {size}\n")
                #elements.append(WritableElement("gfxview", size, f.getvalue(),
                #                                as_page_graphicsview(gfx_name)))

        result.append(WritableElement("tilegfx", size, f.getvalue(),
                                      as_page_tilegfx(bname)))


    return result


def write_constants(outfname):
    with open(outfname, 'w') as f:
        f.write(";; Constants from the pregenerator.\n")
        f.write("C_PLAYER_INVENTORY: EQU {}\n"
                .format(CONSTANT_MAP[TC_INVENTORY_LOC]))
        f.write("C_ITEM_LIMBO: EQU {}\n"
                .format(CONSTANT_MAP[TC_LOST_LOC]))
        f.write("C_PLAYER_LOCATION: EQU {}\n"
                .format(CONSTANT_MAP[TC_PLAYER_LOC]))
        f.write("CMD_USE: EQU {}\n"
                .format(PLAYER_COMMANDS['use']))

def combine_elements(cfg, on_first_page, others):
    fn1 = "pregen/first_page.asm_pregen"
    first_page_index = 2
    key_to_page = {}
    with open("../src/" + fn1, 'w') as f:
        total_size = 0
        for elem in on_first_page:
            f.write(elem.text)
            total_size += elem.length
        assert total_size < PAGE_MAX_SIZE
        key_to_page[elem.pagelabel] = first_page_index
        f.write(f"C_ITEM_PAGE: EQU {first_page_index}\n")

    # unique i makes it so that e won't be reached in comparing things
    elems = [(e.length, i, e) for i, e in enumerate(others)]
    elems.sort(reverse=True)

    first_page_index += 1

    fn2 = "pregen/page_{}.asm_pregen"
    by_page = [(first_page_index - 1, fn1)]
    while len(elems) > 0:
        total_size = 0
        included = []
        page_index = first_page_index
        while True:
            to_remove = []
            for i, entry in enumerate(elems):
                size, i, elem = entry
                if size + total_size < PAGE_MAX_SIZE:
                    total_size += size
                    included.append(elem)
                    to_remove.append(entry)
            print(len(to_remove), len(included))
            if to_remove == []:
                if included != []:
                    print("Writing to page", page_index, "elements", len(included))
                    print("Supposed size", total_size)
                    my_fn = fn2.format(page_index)
                    with open("../src/" + my_fn, 'w') as f:
                        for e in included:
                            f.write(e.text)
                            key_to_page[e.pagelabel] = page_index


                            if e.pagelabel is None:
                                print(e.etype)
                                assert 1 == 0
                    by_page.append((page_index, my_fn))
                    included = []
                    to_remove = []
                    total_size = 0
                    page_index += 1
                else:
                    # We should be completely done now.
                    break
            else:
                elems = [e for e in elems if e not in to_remove]
                to_remove = []
            print("total size", total_size, len(elems), len(included), len(to_remove))

    # Now, make the number of pages a power of 2.
    next_lim = 1
    while next_lim < page_index:
        next_lim *= 2
    print("Page limit", next_lim, "; current last page", page_index)
    while page_index < next_lim:
        my_fn = fn2.format(page_index)
        by_page.append((page_index, my_fn))
        with open("../src/" + my_fn, 'w') as f:
            f.write(";; Empty page, used to make the number of pages a power of 2")
        page_index += 1


    fn3 = "pregen/page_constants.asm_pregen"

    with open("../src/" + fn3, 'w') as f:
        # Constants!
        f.write(";; Page assignment constants \n")
        for key, page_index in sorted(key_to_page.items()):
            f.write("{}: EQU {}\n".format(key, page_index))


    with open("../src/" + "pregen/datapages.asm_pregen", 'w') as f:
        f.write(";; This will contain the main data for the game.\n")
        f.write("INCLUDE \"pregen/page_constants.asm_pregen\" ;; This can be wherever.\n")
        for i, fn in by_page:
            f.write("org	$8000, $BFFF	; page {}\n".format(i))
            f.write(f"    INCLUDE \"{fn}\"\n")
            f.write("    ds PageSize - ($ - 8000h),255\n")


def produce_data(cfg, all_texts, max_itemcount):
    """Main entrypoint."""

    #cfg = ConfigParser()
    #cfg.optionxform = str
    #cfg.read(cfgfile)

    # 1. Collect all items.

    data = read_input(cfg)

    data['page'] = 0

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
    headerfname = cfg['out_files']['chapterheader_output']

    ####

    script_elems = create_script_elements(data, data['scripts'])
    item_core, item_recs = create_item_elements(cfg, data, max_itemcount)

    prepare_graphics(cfg, data)
    split_tilegfx(cfg, data)

    palette_elems = create_palette_elements(cfg, data)
    tilegfx_elems = create_tilegfx_elements(cfg, data)

    generate_huffdict(cfg, data, huffdictfname, all_texts)
    text_elements = create_text_elements(cfg, data)

    write_direction_names(cfg, data, directionsfname)
    write_command_names(data, commandsfname)

    # Create the location file
    location_elements = create_location_elements(data)
    gfxview_elements = create_graphicsview_elements(cfg, data)

    #write_script(data, data['scripts'], scriptfname)

    #write_item(cfg, data, itemfname, itemramfname, max_itemcount)


    write_constants(constantsfname)

    combine_elements(cfg,
                     item_core,
                     item_recs + script_elems + palette_elems + tilegfx_elems +
                     text_elements + location_elements + gfxview_elements)


    #write_graphicsview(cfg, data, locationgfxname)

    # This is for the temporary solution of having one episode on a
    write_chapterheader(cfg, data, headerfname)

    if data['errors']['gfx']:
        print("ERROR! Missing graphics files:")
        print("\n".join(data['errors']['gfx']))
    for k in data['used_strings']:
        if k not in cfg['text']:
            data['errors']['strings'].append(k)
    for k in data['used_scripts']:
        if k not in data['scripts']:
            data['errors']['scripts'].append(k)
    for k in data['used_locations']:
        if k not in data['locations']:
            data['errors']['locations'].append(k)
    if data['errors']['strings']:
        print("ERROR! Missing text entries")
        for missing in sorted(data['errors']['strings']):
            print(f"{missing}=TODO {missing.replace('_', ' ')}")
    if data['errors']['scripts']:
        textend_defaults = ["Look", "Examine"]
        print("ERROR! Missing scripts")
        for missing in sorted(data['errors']['scripts']):
            if any(missing.startswith(v) for v in textend_defaults):
                print(f"SCRIPT {missing}:\n    TEXTEND {missing}")
            else:
                print(f"SCRIPT {missing}:\n    END")
        #print("\n".join(data['errors']['scripts']))
    if data['errors']['locations']:
        print("ERROR! Missing locations")
        print("\n".join(data['errors']['locations']))

    print("Scripts:{} Locations:{} Items:{}".format(len(data['used_scripts']),
                                                    len(data['used_locations']),
                                                    len(data['items'])))


def produce_gfx(cfg):
    #cfg = ConfigParser()
    #cfg.optionxform = str
    #cfg.read(cfgfile)

    produce_regular_gfx.convert_font(
        cfg.get('in_files', 'font'), cfg.get('out_files', 'font')
    )
    produce_regular_gfx.convert_sprite(
        cfg.get('in_files', 'sprites'), cfg.get('out_files', 'sprites')
    )
    produce_regular_gfx.convert_fullscreen(
        cfg.get('in_files', 'title'), cfg.get('out_files', 'title_base')
    )
    produce_regular_gfx.convert_gamescreen(
        cfg.get('in_files', 'ui_view'), cfg.get('out_files', 'ui_view_base')
    )


if __name__ == "__main__":
    # produce_data(os.path.join("content", "samplecontent.cfg"))
    #cfgname = os.path.join("..", "resources", "terraforminggamecontent.cfg")
    #cfgname = os.path.join("..", "resources", "penguingamecontent.cfg")
    cfgname = os.path.join("..", "resources", "step_monolith.cfg")
    cfg = ConfigParser()
    cfg.optionxform = str
    cfg.read(cfgname)

    cfg_files = [cfgname]
    if 'other_chapters' in cfg['general']:
        for fn in cfg['general']['other_chapters'].split(","):
            cfg_files.append(os.path.join(os.path.split(cfgname)[0], fn))

    all_texts = {}
    cfgs = []
    max_itemcount = 0
    for i, fn in enumerate(cfg_files):
        print(i, fn, os.path.exists(fn))
        # 1. Accrue all texts.
        cfg = ConfigParser()
        cfg.optionxform = str
        cfg.read(fn)
        cfgs.append(cfg)
        for k, v in cfg['text'].items():
            all_texts[f"{i}_{k}"] = v
        print("Texts:", len(all_texts))
        itemcount = 0
        for k in cfg:
            if k.lower().startswith("item_"):
                itemcount += 1
        max_itemcount = max(itemcount, max_itemcount)
    print("Text content in total: {}".format(len("".join(all_texts.values()))))
    print("Words: {}".format(len((" ".join(all_texts.values())).split())))
    for i, cfg in enumerate(cfgs):
        print(f":::: Processing file {cfg_files[i]})")
        produce_gfx(cfg)
        produce_data(cfg, all_texts, max_itemcount)
    write_all_item_ram_addresses(cfgs[0]['out_files']['items_RAM_output'], cfgs, max_itemcount)


