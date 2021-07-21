FNAME "jaasta.rom"

org $4000   ; Somewhere out of the way of small basic programs

db "AB" ;   ROM signature
dw start  ; start address
db 0,0,0,0,0,0,0,0,0,0,0,0

; Constants
FORCLR: equ $F3E9
BAKCLR: equ $F3EA
BDRCLR: equ $F3EB
CLIKSW: equ $f3db

CHGCLR: equ $0062
CHGMOD: equ $005F
LINL32: equ $F3AF

WRTPSG: equ $0093
WRTVDP: equ $0047
WRTVRM: equ $004D ; Write to VRAM, A=value, HL=address
RDVRM: equ $004A  ; Read from VRAM, A <- value, HL = address
LDIRVM: equ $005C ; Block transfer from memory to VRAM;
                  ; BC = block length, HL = mem start, DE = start VRAM
LDIRMV: equ $0059
FILVRM: equ $0056 
VDP1_MIRROR: equ $F3E0

GTSTCK: equ $00D5
GTTRIG: equ $00D8 
CALPAT: equ $0084
CALATR: equ $0087

ENASLT:   equ  024h
RSLREG:   equ 0138h

HKEY: equ $FD9F

KEYS: equ $FBE5

;; From :
;; https://www.msx.org/wiki/Develop_a_program_in_cartridge_ROM
PageSize:	equ	04000h	; 16kB
Seg_P8000_SW:	equ	07000h	; Segment switch for page 8000h-BFFFh (ASCII16k)

;; How the different memory pages are used.
;; Page 0, BIOS.
;; Page 1, program code.
;; Page 2, game content, swapped in and out.
;; Page 3, RAM.

;; Pages in game ROM:
;; 0: program code
;; 1: scripts and item records
;; 2: strings
;; 3: strings
;; 4: graphics + locations
;; 5: graphics + locations
;; 6: graphics + locations
;; 7: graphics + locations

;; Maybe actually use only "even" addresses in gfx pages to have twice as many
;; pages for graphics + locations? i.e., the page number would use three bits.

;; The page indices are actually imported constants in constants.asm_pregen?




start: 
	;; Code lifted from Transball
	;; https://github.com/santiontanon/transballmsx
    di
    im 1
    ld sp, $F380    ;; initialize the stack
    ld a, $C9       ;; clear the interrupts
    ld (HKEY), a
    ei
	call Set32KSlot
	call InitializeProgram
	call StartInterrupts
	ld a, 1
	
	jp MainLoop

InitStack:
    di ;; Necessary?
    ld sp, $F380    ;; initialize the stack
    ei
    jp MainLoop

	
MainLoop:
	call TitleScreen
	call GameInit
	call LoadMainGraphics
	call LoadSprites
	call RenderLocationViewport
	call ClearInventoryBox
	call ClearTextbox
	call ExecuteLocationScript
	call ScanLocationHotspots
	call RefreshViewItemList
	call MenuLoop
	jp MainLoop
	
GameInit:
	ld hl, __LOCATION_Home
	ld (PLAYER_LOCATION), hl
	ld a, 0
	ld (POINTER_INDEX), a
	call UpdatePointerY
	call ResetState
	call InitializeItemLocations
	call ClearInventoryBox
	ret
	
WaitForBlank:
	;; Wait for the next VDP blank. Probably could be done
	;; smarter.
	push bc
  .syncLoop:
	ld a, (LATEST_MAIN_STEP)
	ld b, a
  .waitForVDPSync:
	ld a, (LATEST_VDP_INTERRUPT)
	cp b
	jp z, .waitForVDPSync ;; Loop until vblank
	ld (LATEST_MAIN_STEP), a
	pop bc
	ret
	

StartInterrupts:
	ld hl, VideoInterruptHandler
	ld a, $c3
	di
	ld (HKEY), a
	ld (HKEY + 1), hl
	ei
	ret
	
VideoInterruptHandler:
	;;
	ld b, a
	ld a, (LATEST_VDP_INTERRUPT)
	inc a
	ld (LATEST_VDP_INTERRUPT), a
	ld a, b
	ret


ResetState:
	;; Reset the GAME_STATE variables.
	ld bc, 15
	ld a, 0
	ld hl, GAME_STATE
	ld de, GAME_STATE + 1
	ld (hl), a
	ldir
	ret
	
	

MenuLoop:
        ;; Need to clean this up better.
		call TopMenuLoop
		jp MenuLoop

	
InitializeProgram:
	call $00CC ; Disable function key display.

	ld a, 14
	ld (FORCLR), a
	ld a, 1
	ld (BAKCLR), a
	ld (BDRCLR), a
	call CHGCLR

	ld a,2      ; Change screen mode
    call CHGMOD
	
	ld bc, $e201 ;; Should allow 16x16 sprites.
    call WRTVDP

	ld a, 0
	ld (CLIKSW), a	
	ret


;; Load the main graphics to VRAM.
;; TODO: Use constants rather than hard-coded values.
LoadMainGraphics:
	ld a, $11
	ld hl, $2000
	ld bc, 268*8*3
	call FILVRM
	
	ld bc, 256*3
	ld a, $80
	ld hl, $1800
	call FILVRM
	call WaitForBlank
	
	;; First, the text characters. + 3 * 8 because of chars that aren't rendered (terminator, uppercase, newline)
	ld bc, 568 + 8 + 8
	ld de, $0000 + 256 * 8 * 0 + 3 * 8
	ld hl, CHARSET_PATTERNS
	call LDIRVM

	ld bc, 568 + 8 + 8
	ld de, $0000 + 256 * 8 * 1 + 3 * 8
	ld hl, CHARSET_PATTERNS
	call LDIRVM

	ld bc, 568 + 8 + 8
	ld de, $0000 + 256 * 8 * 2 + 3 * 8
	ld hl, CHARSET_PATTERNS
	call LDIRVM
	
	;; Set their colours.
	ld hl, 0 * 8 + $2000
	ld a, $1f
	ld bc, 256 * 8
	call FILVRM	
	ld hl, $2800
	ld a, $1f
	ld bc, 256 * 8
	call FILVRM	
	ld hl, $3000
	ld a, $1e
	ld bc, 256 * 8
	call FILVRM
	
	;; Then the UI graphics.
	ld bc, 240 + 8 + 8
	ld de, LEN_BASECHARS * 8
	ld hl, UIGFX_PATTERNS
	call LDIRVM
	ld bc, 240 + 8 + 8 
	ld de, LEN_BASECHARS * 8 + 256 * 8 * 1
	ld hl, UIGFX_PATTERNS
	call LDIRVM
	ld bc, 240 + 8 + 8
	ld de, LEN_BASECHARS * 8 + 256 * 8 * 2
	ld hl, UIGFX_PATTERNS
	call LDIRVM
	
	ld de, UIGFX_COLOUR_RLE
	ld hl, LEN_BASECHARS * 8 + $2000
	call LoadRLE2VRAM
	ld de, UIGFX_COLOUR_RLE
	ld hl, LEN_BASECHARS * 8 + $2800
	call LoadRLE2VRAM
	ld de, UIGFX_COLOUR_RLE
	ld hl, LEN_BASECHARS * 8 + $3000
	call LoadRLE2VRAM
	
	call ClearUI
	ret
	

;; Viewport-rendering related routines
INCLUDE "viewrender.asm"

;; Itemlist-management related routines
INCLUDE "itemlistmanagement.asm"

;; Script engine
INCLUDE "exec_script.asm"


	

;; Semifunctional Huffman decoder.
;; IX contains the code tree
;; IY is the compressed code.
;; HL is the target where to decompress.
Decompress:
	ld a, (ix)
	ld (END_BYTE), a
	inc ix ;; Points to tree start now.
	push ix
	;; Start reading the compressed data.
    ld bc, 0
  .startNewByte:
	ld a, 0
  .processByte:
	ld c, (iy)
	ld b, 8 ;; The number of bits left.
	
  .cycleBits:
    ld a, (ix)
    bit 0, c
	jp z, .checkIfEnd
  .isOne:
	ld a, (ix + 1)
	jp .checkIfEnd
  .checkIfEnd:
	ld d, 0  ;; Bug: cannot make more than 255 byte jumps.
	ld e, a
	add ix, de
	ld a, (ix + 1) ; If this is 0, then we reached the leaf. 
	cp 0 ;
	jp z, .wasLeaf
	
	jp .nextBit
	
  .wasLeaf:
	ld a, (END_BYTE)
	ld d, (ix)
	cp d
	jp z, .endDecomp
	ld (hl), d
	inc hl 
	ld a, 0
	pop ix ;; Return to tree root
	push ix
	jp .nextBit
	
  .nextBit:
	sra c
	djnz .cycleBits
	inc iy
	jp .processByte
	
  .endDecomp:
    pop ix 
	ret	

	
GetTextToBuffer:
	;; IY = pointer to compressed text location.
	
	call ClearTextbox
	;; First, unpack text to TEXT_BUFFER.
	ld ix, TEXT_HUFFDICT
	ld hl, TEXT_BUFFER
	call Decompress
	ld hl, TEXT_BUFFER
	ld de, TEXTWINDOW
	call DecodeText_HL2DE
	ret
	
	
GetTextToLineBuffer:
	;call ClearTextbox
	;; First, unpack text to TEXT_BUFFER.
	ld ix, TEXT_HUFFDICT
	ld hl, TEXT_BUFFER
	call Decompress
	ld hl, TEXT_BUFFER
	
	ld bc, C_LINEBUFFER_LENGTH - 1
	ld a, CHAR_SPACE
	ld hl, LINEBUFFER
	ld de, LINEBUFFER + 1
	ld (hl), a
	ldir	
	ld hl, TEXT_BUFFER
	ld de, LINEBUFFER
	call DecodeText_HL2DE
	ret	

	
;; Read unpacked, encoded data from a memory address until terminator (0).
;; Encoding: byte 1 means the next letter is in upper case.
DecodeText_HL2DE:
		ld b, 0
	.loopStart:
		ld a, (hl)
		inc hl
		cp 1  ;; Signals uppercase
		jp z, .uppercase
		cp 0  ;; Signals termination
		ret z
		cp 2 ;; Signals end-of-line, not implemented
	.addOffset:
		add a, b
		ld b, 0
		ld (de), a 
		inc de
		jp .loopStart
	.uppercase:
		ld b, 26
		jp .loopStart


;; CORE GAME LOOP
;; Cursor is in the location/item list.
TopMenuLoop:
		call DisplayObjectPrompt
	.noRedrawPrompt:
		call RenderPointer
		;; React to cursor/fire
		call CheckControls
		ld a, (CONTROL_READ)
		cp 0
		jp z, TopMenuLoop
		cp 9
		jp c, .joystickRead
		cp 16
		jp z, .firePressed
		cp 32
		jp z, .cancelPressed
		jp TopMenuLoop
		;;
	.joystickRead:
		cp 1 ;; Move up?
		jp z, .moveUp
		cp 5
		jp z, .moveDown
		jp TopMenuLoop
	.firePressed:
		call CommandMenuLoop
		jp .update
		jp TopMenuLoop
	.cancelPressed:
		;; TODO: Go to a main menu that doesn't exist yet?
		jp TopMenuLoop
		
	.moveUp:
		ld a, (VIEW_ITEM_OFFSET)
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		cp 0
		jp z, TopMenuLoop ;; Already topmost.
		dec a
		ld (VIEW_ITEM_CHOSEN), a
		cp c
		jp nc, .update
		ld b, C_ITEM_LIST_VISIBLE_LEN
		ld a, c
		sub b
		ld (VIEW_ITEM_OFFSET), a
		jp .updateList

		;; 
	.moveDown:
		ld a, (VIEW_ITEM_OFFSET)
		ld b, a
		ld a, (VIEW_ITEM_LENGTH)
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		inc a
		cp c
		jp nc, TopMenuLoop ;; Already last.
		ld (VIEW_ITEM_CHOSEN), a
		
		;; Now, is this >= than (VIEW_ITEM_OFFSET) + C_ITEM_LIST_VISIBLE_LEN?
		
		ld a, C_ITEM_LIST_VISIBLE_LEN
		add a, b
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		cp c
		jp c, .update
		ld a, c
		ld (VIEW_ITEM_OFFSET), a
		jp .updateList
		
	.updateList:
		call RefreshViewItemList
	
	.update: ;; Update sprite location etc.
		ld a, (VIEW_ITEM_OFFSET)
		ld b, a
		ld a, (VIEW_ITEM_CHOSEN)
		sub b
		ld (POINTER_INDEX), a
		call UpdatePointerY
		call RenderPointer
		jp TopMenuLoop

TargetMenuLoop:
		;; Handles the selection of the target object for "USE"
		;; Display same items as for the first object.
		call ClearInventoryBox
		
		ld a, (VIEW_ITEM_CHOSEN)
		ld c, a
		ld a, (VIEW_ITEM_OFFSET)
		ld b, a
		
		ld a, 0
		ld (POINTER_INDEX), a
		ld (COMMAND_LIST_INDEX), a
		ld (VIEW_ITEM_CHOSEN), a
		ld (VIEW_ITEM_OFFSET), a

		push bc ;; This is for restoring the view item options if canceling.
		call RefreshViewItemList
		
		call DisplayTargetPrompt
		
		call UpdatePointerY
		call RenderPointer
		
		
	.controlLoop:
		call CheckControls
		ld a, (CONTROL_READ)
		cp 0
		jp z, .controlLoop
		cp 9
		jp c, .joystickRead
		cp 16
		jp z, .firePressed
		cp 32
		jp z, .cancelPressed
		jp .controlLoop
		;;
	.joystickRead:
		cp 1 ;; Move up.
		jp z, .moveUp
		cp 5
		jp z, .moveDown
		jp .controlLoop
	.firePressed:
		pop bc
		ld a, (VIEW_ITEM_CHOSEN)
		ld de, VIEW_ITEM_LIST
		ld h, 0
		ld l, a
		add a, a
		add a, l
		ld l, a
		add hl, de
		;; HL points to the chosen view item.
		;; OBJECT_ADDR is a copy of the list entry.
		ld a, (hl)
		ld (OBJECT_ADDR), a
		inc hl
		call UnrefHL
		ld (OBJECT_ADDR + 1), hl
		ret

	.cancelPressed:
		;; Mark nothing as chosen, return up.
		ld a, 0
		ld (OBJECT_ADDR), a
		ld (OBJECT_ADDR + 1), a
		ld (OBJECT_ADDR + 2), a
		pop bc
		ld a, b
		ld (VIEW_ITEM_OFFSET), a
		ld a, c
		ld (VIEW_ITEM_CHOSEN), a
		ret
		
	.moveUp:
		ld a, (VIEW_ITEM_OFFSET)
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		cp 0
		jp z, .controlLoop ;; Already topmost.
		dec a
		ld (VIEW_ITEM_CHOSEN), a
		cp c
		jp nc, .update
		ld b, C_ITEM_LIST_VISIBLE_LEN
		ld a, c
		sub b
		ld (VIEW_ITEM_OFFSET), a
		jp .updateList

	.moveDown:
		ld a, (VIEW_ITEM_OFFSET)
		ld b, a
		ld a, (VIEW_ITEM_LENGTH)
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		inc a
		cp c
		jp nc, .controlLoop ;; Already last.
		ld (VIEW_ITEM_CHOSEN), a
		
		;; Now, is this >= than (VIEW_ITEM_OFFSET) + C_ITEM_LIST_VISIBLE_LEN?
		
		ld a, C_ITEM_LIST_VISIBLE_LEN
		add a, b
		ld c, a
		ld a, (VIEW_ITEM_CHOSEN)
		cp c
		jp c, .update
		ld a, c
		ld (VIEW_ITEM_OFFSET), a
		jp .updateList
		
	.updateList:
		call RefreshViewItemList
	
	.update: ;; Update sprite location etc.
		ld a, (VIEW_ITEM_OFFSET)
		ld b, a
		ld a, (VIEW_ITEM_CHOSEN)
		sub b
		ld (POINTER_INDEX), a
		call UpdatePointerY
		call RenderPointer
		jp .controlLoop		

		
;; The menu shows available commands for item.
CommandMenuLoop:
		call ClearInventoryBox
		call ScanObjectCommands
		call RenderCommandList
		
		call DisplayVerbPrompt
		
		ld a, 0
		ld (POINTER_INDEX), a
		ld (COMMAND_LIST_INDEX), a
		ld (COMMAND_EXECUTED), a
		
		call UpdatePointerY
		call RenderPointer
	
	.controlLoop:
		call CheckControls
		;; React to cursor/fire
		ld a, (CONTROL_READ)
		cp 32
		jp z, .cancelPressed
		cp 16
		jp z, .firePressed
		cp 0
		jp z, .controlLoop
		jp .joystickRead
		
	.cancelPressed:
		call RefreshViewItemList
		call DisplayObjectPrompt
		ret
	.firePressed:
		ld a, (COMMAND_LIST_INDEX)
		ld e, a
		ld d, 0
		ld l, a
		ld h, 0
		add hl, hl
		add hl, de
		ld de, COMMAND_LIST	
		add hl, de
		ld a, (hl)
		
		cp CMD_USE
		jp z, .getTarget
		
		inc hl
		call UnrefHL
		call ExecuteScriptHL
		jp .commandCleanup
		
	.getTarget:
		inc hl
		push hl
		call TargetMenuLoop
		pop hl
		ld a, (OBJECT_ADDR)
		cp 0
		jp z, .canceledTarget
		call UnrefHL
		call ExecuteScriptHL
		jp .commandCleanup
		
	.canceledTarget:
		call ClearInventoryBox
		call RenderCommandList
		call DisplayVerbPrompt
		ld a, (COMMAND_LIST_INDEX)
		ld (POINTER_INDEX), a
		call UpdatePointerY
		call RenderPointer
		
		jp .joystickRead
		
	.commandCleanup:
		ld a, 1
		ld (COMMAND_EXECUTED), a
		call ScanLocationHotspots
		call RefreshViewItemList		
		ret
	
	.joystickRead:
		cp 1
		jp z, .movingUp
		cp 5
		jp z, .movingDown
		jp .controlLoop
	.movingUp:
		ld a, (COMMAND_LIST_INDEX)
		cp 0
		jp z, .controlLoop
		dec a
		jp .updatePointer
	.movingDown:
		ld a, (COMMAND_LIST_LENGTH)
		ld b, a
		ld a, (COMMAND_LIST_INDEX)
		inc a
		cp b
		jp nc, .controlLoop
		ld (COMMAND_LIST_INDEX), a
		
	.updatePointer:
		ld (COMMAND_LIST_INDEX), a
		ld (POINTER_INDEX), a
		call UpdatePointerY
		call RenderPointer
		jp .controlLoop
	
	jp .controlLoop


ExecuteLocationScript:
		;; Load the address of the entrance script for the current location
		;; and execute it.
		ld hl, (PLAYER_LOCATION)
		ld de, 2+2+2
		add hl, de
		ld b, (hl)
		ld de, 4
		ld a, b
		inc hl
		cp 0
		jp z, .execute		
	.loop:
		add hl, de
		djnz .loop
	.execute:
		call UnrefHL
		;; HL now points to the start script.
		call ExecuteScriptHL
		ret
	

ClearInventoryBox:
		;; Clears the display for the menu on the right.
		ld hl, $1800 + 32 + 17 ; VRAM addr
		ld bc, 14 * 256 + 14
		ld de, 32 - 14
		
	.loop:
		ld a, CHAR_SPACE
		call WRTVRM
		inc hl
		djnz .loop
		ld b, 14
		add hl, de
		dec c
		jp nz, .loop
		ret 
		
		
RenderCommandList:
	;; Command ID, script address
		ld de, $1800 + 32 + 17 + 32 + 1
		ld (LOOPVARS), de

		ld a, (COMMAND_LIST_LENGTH)
		ld c, a

	.onlyRemainder:
		ld b, a ;; How many items are left to handle.
		;ld a, c
		;; Mul A by 3 to get the offset in list.
		;rlca
		;add a, c
		;ld e, a
		;ld d, 0
		ld hl, COMMAND_LIST ;VIEW_ITEM_LIST
		;add hl, de ;; Now points to the first item to render.
		
	.nextVerb:
		push hl
		push bc
		ld a, (hl)
		push hl
		ld hl, (LOOPVARS) ;; VRAM addy
		;call WRTVRM
		;ld hl, (LOOPVARS)
		inc hl
		ld (LOOPVARS), hl		
		
		pop hl
		ld a, (hl)
		inc hl
		
		;; A has the verb index.
		;; HL points to the start of script.
		ld hl, COMMAND_NAMES
		rlca
		ld e, a
		ld d, 0
		add hl, de
		call UnrefHL ;; Now HL points to the command name.
		ld (LOOPVARS2), hl
		;; That is also the name of the item.

		call FillTextBufferWithSpace
		ld iy, (LOOPVARS2)
		call GetTextToLineBuffer
		
		ld hl, LINEBUFFER
		ld bc, 13 - 1
		ld de, (LOOPVARS)
		call LDIRVM
		ld de, (LOOPVARS)
		ld hl, 31
		add hl, de
		ld (LOOPVARS), hl
		
	.endItemLoop:
		pop bc
		pop hl
		inc hl
		inc hl
		inc hl
		djnz .nextVerb
	ret


ScanObjectCommands:
		;; Populate the list of verbs for the chosen object.
		;; Input is given via VIEW_ITEM_CHOSEN and VIEW_ITEM_LIST.
		ld a, 0
		ld (COMMAND_LIST_INDEX), a
		ld (COMMAND_LIST_LENGTH), a
		ld hl, COMMAND_LIST
		ld (LOOPVARS), hl
		
		ld a, (VIEW_ITEM_CHOSEN)
		ld l, a
		ld h, 0
		add hl, hl
		ld d, 0
		ld e, a
		add hl, de ;; HL <- A * 3
		ld de, VIEW_ITEM_LIST
		add hl, de
		;; HL <- pointer to the item record.
		ld a, (hl)
		inc hl
		cp C_ITEM_DIRECTION
		jp z, .isDirection
		jp .isItem
	
	.isDirection:
		ld a, (hl)
		ld c, a
		;; A = direction code
		ld hl, (PLAYER_LOCATION_DIRECTIONS)
		ld b, (hl)
		inc hl
	.loopDirections:		
		ld a, (hl)
		cp c
		jp z, .processThisDirectionScript
		ld de, 4
		add hl, de
		jp .endLoopDirections
	.processThisDirectionScript:
		inc hl
		ld a, (hl) ;; command id
		ld (ADD_TO_VIEW_LIST), a
		inc hl
		push hl
		call UnrefHL
		ld (ADD_TO_VIEW_LIST + 1), hl
		;ld (ADD_TO_VIEW_LIST + 2), h
		call .addVerbToList
		pop hl
		ld de, 2
		add hl, de
		jp .endLoopDirections
		
	.endLoopDirections:
		djnz .loopDirections
		ret
		
	.addVerbToList:
		call AddCommandToList
		ret

	
	.isItem:
		call UnrefHL
		ld de, 4
		add hl, de
		ld b, (hl) ;; Number of scripts.
		;; HL = item address.
		inc hl
		ld iy, ADD_TO_VIEW_LIST
		
	.loopItemScripts:
		push bc
		ld a, (hl) ;; Command name.
		ld (iy), a
		inc hl
		ld a, (hl)
		ld (iy + 1), a
		inc hl
		ld a, (hl)
		ld (iy + 2), a		
		push hl
		call AddCommandToList
		pop hl
		;ld de, 3
		;add hl, de
		inc hl
		pop bc
		djnz .loopItemScripts
		ret
		
		
AddCommandToList:
		push bc
		ld a, (COMMAND_LIST_LENGTH)
		ld e, a
		rlca
		add a, e ;; Multiplied by 3
		ld d, 0
		ld e, a
		ld hl, COMMAND_LIST
		add hl, de
		ld a, (ADD_TO_VIEW_LIST)
		ld (hl), a
		inc hl
		ld a, (ADD_TO_VIEW_LIST + 1)
		ld (hl), a
		inc hl
		ld a, (ADD_TO_VIEW_LIST + 2)
		ld (hl), a

		ld hl, COMMAND_LIST_LENGTH
		inc (hl)
		pop bc
		ret				
	

;; Clears the contents in the text box.
ClearTextbox:
		ld bc, 6 * 30 - 1
		ld a, CHAR_SPACE
		ld hl, TEXTWINDOW
		ld de, TEXTWINDOW + 1
		ld (hl), a
		ldir
		call FillTextBufferWithSpace
		call UpdateTextBoxInFullFast
		ret

FillTextBufferWithSpace:
		ld bc, C_TEXT_BUFFER_LENGTH - 1
		ld a, CHAR_SPACE
		ld hl, TEXT_BUFFER
		ld de, TEXT_BUFFER + 1
		ld (hl), a
		ldir
		ret
	

RenderLocationDescription:
		ld hl, (PLAYER_LOCATION)
		call UnrefHL
		call DisplayTextHL
		ret
		
DisplayTextHL:
		push hl
		call FillTextBufferWithSpace
		pop iy
		call GetTextToBuffer
		call UpdateTextBoxInFullSlow
		ret
		
	
UpdateTextBoxInFullFast:
		ld de, $1A00 + 33
		ld (RENDER_HELP), de
		ld hl, TEXTWINDOW
		ld (LOOPVARS2), hl
		ld b, 6
	.rowloop:
		ld a, b
		ld (LOOPVARS), a
		ld bc, 30
		ld de, (RENDER_HELP)
		ld hl, (LOOPVARS2)
		call LDIRVM
		ld de, (RENDER_HELP)
		ld hl, 32
		add hl, de
		ld (RENDER_HELP), hl
		ld de, (LOOPVARS2)
		ld hl, 30
		add hl, de
		ld (LOOPVARS2), hl
		ld a, (LOOPVARS)
		ld b, a
		djnz .rowloop
		ret


		
UpdateTextBoxInFullSlow:

		ld de, $1A00 + 33
		ld (RENDER_HELP), de
		ld b, 6

		ld a, 1
		ld (TEXT_DELAY_ACTIVE), a		
		ld hl, TEXTWINDOW
		ld (LOOPVARS2), hl
		
	.rowloopClear:
		push bc
		ld a, CHAR_SPACE
		ld bc, 30
		ld hl, (RENDER_HELP)
		call FILVRM
		ld de, (RENDER_HELP)
		ld hl, 32
		add hl, de
		ld (RENDER_HELP), hl
		pop bc
		djnz .rowloopClear


		ld de, $1A00 + 33
		ld (RENDER_HELP), de
		ld hl, TEXTWINDOW
		ld (LOOPVARS2), hl
		ld b, 6
		
	.rowloop:
		ld a, b
		ld (LOOPVARS), a
		ld b, 30
		ld de, (RENDER_HELP)
		ld hl, (LOOPVARS2)
		
	.columnloop:
		ld a, (hl)
		cp CHAR_SPACE
		jp z, .nowrite
		ex de, hl
		push de
		push hl
		push bc
		call WRTVRM
		call .characterTypeDelay
		pop bc 
		pop hl
		pop de
		ex de, hl
		
	.nowrite:
		inc de
		inc hl
		djnz .columnloop
		
		ld de, (RENDER_HELP)
		ld hl, 32
		add hl, de
		ld (RENDER_HELP), hl
		ld de, (LOOPVARS2)
		ld hl, 30
		add hl, de
		ld (LOOPVARS2), hl
		
		ld a, (LOOPVARS)
		ld b, a
		djnz .rowloop
		;call WaitForFireButton
		
		ret

	.characterTypeDelay:
		ld a, (TEXT_DELAY_ACTIVE)
		and a
		ret z
		ld b, 1
	.delayLoop:
		call WaitForBlank
		push bc
		call CheckControls
		ld a, (CONTROL_READ)
		cp 16
		jp nz, .afterDelayLoop
		ld a, 0
		ld (TEXT_DELAY_ACTIVE), a
		pop bc
		ret
		
	.afterDelayLoop:
		pop bc
		djnz .delayLoop		
		ret		


UpdatePlayerLocation:
		ld hl, (PLAYER_LOCATION)
		ld de, 4 + 2
		add hl, de
		ld (PLAYER_LOCATION_DIRECTIONS), hl
		ret

		
UnrefHL:
    ;; Read the values in (HL) and (HL+1),
    ;; save those values in HL instead.

	    push de
	    ld e, (hl)
	    inc hl
	    ld d, (hl)
	    ex de, hl
	    pop de
	    ret


;; -----------------------------------------------------------------------------
;; Routines to handle changing pages.
;; Usage: call the matching Decode*RefHL routine (typically NOT DecodeRefHL
;; directly).
;; This will change the page. The new page name is stored in STACK, which means
;; you have to call PopAndChangePage.
;; -----------------------------------------------------------------------------

PageMask:
        ;; Page mask = (HL >> 12) & 3
        ;; Then also add (PAGE_BASE_INDEX) to get the correct page.
        ld a, h
        rlca
        rlca
        and 3
        push bc
        ld b, a
        ld a, (PAGE_BASE_INDEX)
        add a, b
        pop bc
        ret

DecodeRefHL:
        ;; Read the HL, interpret it as a location record, read the page from
        ;; the address.
        ;; The two most significant bits in HL tell the type-specific page index.
        call UnrefHL ;; HL will contain the "coded" address
        call PageMask ;; Read the coded address from HL

        ;; Now A has the "location page number" 0-3.
        call PushAndChangePage
        ;; Fix the address in HL
        ld a, 63 ;; 00111111b
        and h
        xor 128 ;; 10000000b, set the address to correct slot.
        ld h, a ;; Now HL points to the correct address.
        ret


;DecodeItemRefHL:
;        ld a, C_PAGE_ITEM_BASE
;        ld (PAGE_BASE_INDEX), a
;        jp DecodeRefHL


;DecodeScriptRefHL:
;        ld a, C_PAGE_SCRIPT_BASE
;        ld (PAGE_BASE_INDEX), a
;        jp DecodeRefHL


;DecodeLocationRefHL:
;    ;; We might want to do this differently.
;        ld a, C_PAGE_LOCATION_BASE
;        ld (PAGE_BASE_INDEX), a
;        jp DecodeRefHL


;DecodeTextRefHL:
;        ld a, C_PAGE_TEXT_BASE
;        ld (PAGE_BASE_INDEX), a
;        jp DecodeRefHL


PushAndChangePage:
        ;; Pushes the current page to stack, then reads from A the new page to load.
        push af
        ;; Is the new page other than the current? If yes, change the page.
        push bc
        ld b, a
        ld a, (PAGE_TEMP)
        cp b
        jp z, .clear
        ld a, b
        ld	(Seg_P8000_SW),a
        ld (CURRENT_PAGE), a
    .clear:
        pop bc
        ret


PopAndChangePage:
        ;; Reads the previous page from stack.
        pop af
        push bc
        ld b, a
        ld a, (CURRENT_PAGE)
        cp b
        jp z, .clear
        ;; Is the previous page other than the current? If yes, change the page.
        ld	(Seg_P8000_SW),a
        ld (CURRENT_PAGE), a
    .clear:
        pop bc
        ret

	
DisplayTargetPrompt:
		ld iy, __TXT_SelectTarget
		jp DisplayPrompt	
DisplayVerbPrompt:
		ld iy, __TXT_SelectVerb
		jp DisplayPrompt
DisplayObjectPrompt:
		ld iy, __TXT_SelectObject
		jp DisplayPrompt
	
DisplayPrompt:
		call GetTextToLineBuffer
		ld bc, 13
		ld de, $1800 + 50
		ld hl, LINEBUFFER
		call LDIRVM
		ret


;; Initialize item locations
InitializeItemLocations:
		ld hl, ITEM_ADDRESS_LIST
		ld e, (hl)
		ld d, 0
		ex de, hl
		add hl, hl
		ld b, h
		ld c, l
		
		ld hl, ITEM_INIT_LOCATIONS
		ld de, ITEM_RAM_LOCATIONS
		ldir		
		ret


;; Reading controls as actions.
;; These hides the user inputs from the caller.
;; Cursor left == cancel
;; Second joystick button == cancel
ReadStick:
		ld a, 0
		call GTSTCK
		cp 7
		jp z, .isCancel
		and a
		
		ret nz
		ld a, 1
		call GTSTCK
		ret
	.isCancel:
		ld a, 32
		ret

ReadButton:
		ld a, 0
		call GTTRIG
		cp 255
		jp z, .wasFire
		;; TODO: Replace with ESCAPE reading from KEYS
		ld a, 0
		cp 255
		jp z, .wasCancel
		ld a, 1
		call GTTRIG
		cp 255
		jp z, .wasFire
		ld a, 3
		call GTTRIG
		cp 255
		jp z, .wasCancel
		ret
	.wasFire:
		ld a, 16
		ret
	.wasCancel:
		ld a, 32
		ret
		
CheckControls:
		call WaitForBlank
		ld a, 0
		ld (CONTROL_READ), a
		call ReadStick
		cp 0
		jp z, .resetStickDelay
		ld b, a
		ld a, (STICK_DELAY)
		cp 0
		jp nz, .decreaseStickDelay
		
		ld a, b
		ld (CONTROL_READ), a
		ld a, C_STICK_DELAY
		ld (STICK_DELAY), a
		ret
		
	.resetStickDelay:
		ld a, 0
		ld (STICK_DELAY), a
		jp .checkButtons
		
	.decreaseStickDelay:
		ld a, (STICK_DELAY)
		dec a
		ld (STICK_DELAY), a
		
	.checkButtons:
		call ReadButton
		cp 16
		jp z, .wasPressed
		cp 32
		jp z, .wasPressed
		ld a, 0
		ld (TRIGGER_DELAY), a
		ret
	.wasPressed:
		ld b, a
		ld a, (TRIGGER_DELAY)
		cp 0
		jp nz, .decreaseTriggerDelay
		ld a, b
		ld (CONTROL_READ), a
		ld a, C_TRIGGER_DELAY
		ld (TRIGGER_DELAY), a
		ret
	.decreaseTriggerDelay:
		ld a, (TRIGGER_DELAY)
		dec a
		ld (TRIGGER_DELAY), a
		ret




;;;; UI help

UpdatePointerY:
		ld a, (POINTER_INDEX)
		;; Mul by 8
		rlca
		rlca
		rlca
		;; Add offset
		add a, C_POINTER_OFFSET
		ld (POINTER_Y), a
		ret
		
RenderPointer:
		ld a, 0		
		ld (SPRITE_VALS + 2), a
		call CALATR
		ex de, hl
		ld a, 1
		ld (SPRITE_VALS + 3), a
		ld a, (POINTER_Y)
		ld (SPRITE_VALS), a
		ld a, 136 - 8
		ld (SPRITE_VALS + 1), a
		ld hl, SPRITE_VALS
		ld bc, 4
		call LDIRVM
		ret
		
		

C_POINTER_OFFSET: EQU 16


WaitForFireButton:
		ld a, 8
		ld (SPRITE_VALS + 3), a
		ld a, 4
		ld (SPRITE_VALS + 2), a
		ld a, 240
		ld (SPRITE_VALS + 1), a
		;ld a, 176
		ld a, 168
		ld (SPRITE_VALS), a
	.render:
		ld a, 1
		call CALATR
		ex de, hl
		ld hl, SPRITE_VALS
		ld bc, 4
		call LDIRVM
		ld a, (SPRITE_VALS + 2)
		xor 12
		ld (SPRITE_VALS + 2), a ;; Swap between 1 and 2
		ld b, 20
	.delay:
		push bc
		call WaitForBlank
		call CheckControls
		pop bc
		ld a, (CONTROL_READ)
		cp 16
		jp z, .pressed
		djnz .delay
		jp .render
	.pressed:
		ld a, 192
		ld (SPRITE_VALS), a
		ld a, 1
		call CALATR
		ex de, hl
		ld hl, SPRITE_VALS
		ld bc, 4
		call LDIRVM
		ret
		


LoadSprites:
	;; Loads all sprites used in the game.
	
	ld a, 0
	ld (LOOPVARS), a ;; Temporary use.
  .nextSprite:
	; Copy the sprites.
	ld a, (LOOPVARS)
	call CALPAT
	ex de, hl
	ld hl, SPRITE_GFX
	ld bc, 32
	ld a, (LOOPVARS)

  .startWhile:
	cp 0  
	jp z, .endWhile
	add hl, bc
	dec a
	jp .startWhile
	
  .endWhile:
	CALL LDIRVM
	ld a, (LOOPVARS)
	inc a
	ld (LOOPVARS), a
	cp _NO_OF_SPRITES
	jp nz, .nextSprite
	ret	


Set32KSlot:
;; By ARTRAG, https://www.msx.org/forum/msx-talk/development/memory-pages-again
	call RSLREG
	rrca
	rrca
	and 3
	ld c,a
	add a,0xC1
	ld l,a
	ld h,0xFC
	ld a,(hl)
	and 080h
	or c
	ld c,a
	inc l
	inc l
	inc l
	inc l
	ld a,(hl)
	and 0x0C
	or c           ; in A the rom slotvar 
	ld h,080h    
	jp ENASLT
	
end_coreCode:


;; Include graphics binaries

UIGFX_COLOUR_RLE: incbin "incbins/gfx_ui_colours.bin"
UIGFX_EMPTY_SCREEN_RLE: incbin "incbins/gfx_ui_chars_rle.bin"
UIGFX_PATTERNS: incbin "incbins/gfx_ui.bin"
CHARSET_PATTERNS: incbin "incbins/gfx_chars.bin"

UIGFX_TITLESCREEN_GFX: incbin "incbins/gfx_title.bin"
UIGFX_TITLESCREEN_RLE: incbin "incbins/gfx_title_chars_rle.bin"
UIGFX_TITLESCREEN_CRLE: incbin "incbins/gfx_title_colours.bin"

;; When reusing the engine, you can replace this.
TitleScreen:
		;; Render the title screen.
		call WaitForBlank
		;; 1. Wipe all colourcoding.
		ld bc, 256*8
		ld hl, $2000
		ld a, 1
		call FILVRM
		;; 2. Unpack gfx coding.
		ld hl, UIGFX_TITLESCREEN_GFX
		ld de, 0
		ld bc, UIGFX_TITLESCREEN_RLE - UIGFX_TITLESCREEN_GFX
		call LDIRVM
		ld hl, UIGFX_TITLESCREEN_GFX
		ld de, $800
		ld bc, UIGFX_TITLESCREEN_RLE - UIGFX_TITLESCREEN_GFX
		call LDIRVM
		ld hl, UIGFX_TITLESCREEN_GFX
		ld de, $1000
		ld bc, UIGFX_TITLESCREEN_RLE - UIGFX_TITLESCREEN_GFX
		call LDIRVM
		
		;; 3. Unpack RLE
		ld de, UIGFX_TITLESCREEN_RLE
		ld hl, $1800
		call LoadRLE2VRAM
		;; 4. Unpack colour RLE.
		call WaitForBlank
		ld de, UIGFX_TITLESCREEN_CRLE
		ld hl, $2000
		call LoadRLE2VRAM
		ld de, UIGFX_TITLESCREEN_CRLE
		ld hl, $2800
		call LoadRLE2VRAM
		ld de, UIGFX_TITLESCREEN_CRLE
		ld hl, $3000
		call LoadRLE2VRAM
		
	.loop:
		call CheckControls
		ld a, (CONTROL_READ)
		cp 16
		ret z
		jp .loop



;;;;;; Data included from the conversions.

DIRECTIONS: ;; Set of Huffman-encoded strings
		INCLUDE "pregen/directions.asm_pregen"
		INCLUDE "pregen/commands.asm_pregen"
TEXT_HUFFDICT:
		INCBIN "incbins/textdictionary.huffarc"

SPRITE_GFX:
		INCBIN "incbins/gfx_sprites.bin"
		
end_permanentData:

;; These should all fit in one 16K page.
;; TODO: Save TILE_COLOUR_TABLE and TILE_PATTERN_TABLE in RAM
;; TODO: Save ITEM_ADDRESS_LIST and ITEM_INIT_LOCATIONS

;; Fill in the extra space of the page.
ds ((($-1)/$4000)+1)*$4000-$

TILEGFX:
        ;; THIS HAS TO HAVE CONSTANT ADDRESSING ACROSS PAGES!
		INCLUDE "pregen/tilegfx.asm_pregen"
        ;; THIS HAS TO HAVE CONSTANT ADDRESSING ACROSS PAGES!
		INCLUDE "pregen/items_rom.asm_pregen"

		INCLUDE "pregen/scripts.asm_pregen"

LOCATION_RECORDS:
		INCLUDE "pregen/locations.asm_pregen"
PALETTES:
		INCLUDE "pregen/palette.asm_pregen"
GFXVIEWS:
        INCLUDE "pregen/gfxview.asm_pregen"
TEXTS:
		INCLUDE "pregen/texts.asm_pregen"


		

;; RAM
endadr: ds ((($-1)/$4000)+1)*$4000-$

org $c800
		INCLUDE "pregen/items_ram.asm_pregen"


LATEST_VDP_INTERRUPT: RB 1
END_BYTE: RB 1

PLAYER_LOCATION: RW 1 ;; Memory pointer to the location record
PLAYER_LOCATION_DIRECTIONS: RW 1 ;; Memory pointer to inside the location record

ITEM_LOCATIONS: RB 3 * ITEM_COUNT ;; Memory pointers to the item locations.

TEXTWINDOW: RB 30*6 ;; Not 32*8 to leave margins.

C_LINEBUFFER_LENGTH: EQU 20

LINEBUFFER: RB C_LINEBUFFER_LENGTH

GAME_STATE: RB 16 ;; Probably overkill.

COMMAND_LIST: RB C_ITEM_LIST_VISIBLE_LEN * 4 ;; 4 bytes per command; code + script address, one byte extra for now.

CONTROL_READ: RB 1 ;; 0 = nothing, 1-8 = stick, 16 = fire pressed, 32 = esc/fire2 pressed

ITEM_COUNT: EQU 20

VIEW_ITEM_LIST: RW 100 ;; Addresses to directions, hotspots, items present.
VIEW_ITEM_LENGTH: RB 1
VIEW_ITEM_OFFSET: RB 1
VIEW_ITEM_CHOSEN: RB 1

POINTER_INDEX: RB 1
POINTER_Y: RB 1		

TEXT_BUFFER: RB C_TEXT_BUFFER_LENGTH
RENDER_HELP: RW 1
LOOPVARS: RW 1
LOOPVARS2: RW 1

ADD_TO_VIEW_LIST: RB 3 ;; Type (1B), mem address for it (2B)

LEN_BASECHARS: EQU 75
LEN_UICHARS: EQU 30
VIEW_CHAR_START: EQU LEN_BASECHARS + LEN_UICHARS
CHAR_SPACE: EQU 55
CHAR_DIGIT_0: EQU 56
CHAR_LOWER_A: EQU 3
CHAR_UPPER_A: EQU 29

C_VISIBLE_LIST_LENGTH: EQU 13 

C_ITEM_LOCAL_ICON: EQU 89
C_ITEM_INVENTORY_ICON: EQU 88
C_ITEM_DIRECTION: EQU 85

C_TEXT_BUFFER_LENGTH: EQU 14*14 * 2

TRIGGER_DELAY: RB 1
STICK_DELAY: RB 1		
C_STICK_DELAY: equ 23
C_TRIGGER_DELAY: equ 41		

COMMAND_LIST_INDEX: RB 1
COMMAND_LIST_LENGTH: RB 1

_NO_OF_SPRITES: EQU 3

SPRITE_VALS: RB 4

OBJECT_ADDR: RB 3

COMMAND_EXECUTED: RB 1

TEXT_DELAY_ACTIVE: RB 1

LATEST_MAIN_STEP: RB 1

CURRENT_PAGE: RB 1 ;; Which ROM page is currently displayed.
PAGE_TEMP: RB 1 ;; Help in keeping the current page number
PAGE_BASE_INDEX: RB 1
C_ITEM_LIST_VISIBLE_LEN: equ 14

INCLUDE "pregen/constants.asm_pregen"
