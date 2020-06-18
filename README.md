# jaassa
Jäässä (MSX)

Jäässä is a simple adventure game for MSX, originally released in 2020. It is also a sample for a graphical adventure game engine.

The repo contains both the source code for the game and the Python scripts used to convert the data (text files and PNG images) for inclusion in the game.

The ASM source code is written for tniASM, for which the conversion tools also produce binaries etc.

How to compile:
---------------

1. You need a Python3 environment with Pillow installed.
2. In python/, execute generate_content.py and produce_regular_gfx.py
3. Go to src/, run tniasm.exe main.asm (you need to have downloaded tniASM first; v0.45 works)

Basics:
-------

python/generate_content.py reads resources/penguingamecontent.cfg and goes on to compress all the resources needed in the actual game.
python/produce_regular_gfx.py has hardcoded locations for title graphics, main screen, font and sprites.

See resources/penguingamecontent.cfg; that file contains all the data for items, locations etc.
See resources/penguingamescripts.script; that file contains the scripts the engine will invoke.
