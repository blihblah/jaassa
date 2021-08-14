;; Routines that render the 14x14 character location viewport.

;; Render the location.
RenderLocationViewport:
        ;; Reset the view to black for redrawing.
		call ResetView
		call PlayMovementSound
		ld hl, (PLAYER_LOCATION)
		inc hl
		inc hl
		ld e, (hl)
		inc hl
		ld d, (hl)
		inc hl
		push hl
		call UnpackTilePalette
		pop hl
		call UnrefHL
		push hl

		;; Now, loop through the tiles.
		;; First 7 lines with 14 tiles on each.
		ld b, 7 * 14
		ld de, VIEW_CHAR_START * 8 + $0000
		ld (RENDER_HELP), de
		ld (LOOPVARS), hl
		call .singleLoop
		;; Second 7 lines
		ld b, 7 * 14
		ld de, VIEW_CHAR_START * 8 + $0800 ; $1000
		ld (RENDER_HELP), de		
		call .singleLoop

		;; Now, the colour table.
		call UnpackColourTable
		call WaitForBlank

		pop hl
		ld (LOOPVARS), hl

		;; First 7 lines
		ld b, 7 * 14
		ld de, VIEW_CHAR_START * 8 + $2000
		ld (RENDER_HELP), de
		call .singleLoop
		;; Second 7 lines
		ld b, 7 * 14
		ld de, VIEW_CHAR_START * 8 + $2800
		ld (RENDER_HELP), de
		call .singleLoop
		ret
	
	.singleLoop:
		ld hl, (LOOPVARS) ;; This is the pointer to the location record byte
		ld a, (hl) ;; Which index.
		ld d, 0
		ld e, a
		ld hl, TEXT_BUFFER
		add hl, de
		add hl, de ;; Multiply by 2 to get offset to palette start
		ld e, (hl)
		inc hl
		ld d, (hl)
		ex de, hl
		;; HL now points to the correct tile pattern start.
		call .writePattern
		
		ld hl, (LOOPVARS)
		inc hl
		ld (LOOPVARS), hl
		
		djnz .singleLoop
		ret
		
	.writePattern:
		;; HL = memory location, DE = VRAM location.
		push de
		push hl
		push bc
		ld bc, 8
		ld de, (RENDER_HELP)
		call LDIRVM
		ld de, (RENDER_HELP)
		ld hl, 8
		add hl, de
		ld (RENDER_HELP), hl
		pop bc
		pop hl 
		pop de
		ret

;; Resets the view for a new location.
ResetView:
		;; Write black colour code for all view tiles
		ld hl, VIEW_CHAR_START * 8 + $2000
		ld bc, 7 * 14 * 8 ;; 
		ld a, $11  
		call FILVRM		
		ld hl, VIEW_CHAR_START * 8 + $2800
		ld bc, 7 * 14 * 8 ;; 
		ld a, $11  
		call FILVRM
		
		call WaitForBlank
	
		;; Fill in the view.
		ld de, RENDER_HELP
		ld a, VIEW_CHAR_START
		ld (de), a
		
		ld c, 7  ;; 7 row pairs
		ld hl, $1800 + 32 + 1
	.nextRow:
		ld b, 14 ;; 14 columns
	.nextColumn:
		push hl
		ld a, (de)
		call WRTVRM
		
		ld de, 7 * 32
		add hl, de
		ld de, RENDER_HELP
		ld a, (de)
		call WRTVRM

		ld a, (de)
		inc a
		ld (de), a
		pop hl
		inc hl
		djnz .nextColumn
		
		ld de, 32 - 14
		add hl, de

		ld de, RENDER_HELP
		dec c
		jp nz, .nextRow		
		ret


UnpackTilePalette:
		;; Unpacks the palette in DE to TEXT_BUFFER.
		;; Packed palette describes which tiles belong in the image using
		;; run-length encoding.
		push bc
		push hl

		ld hl, TEXT_BUFFER
		ld bc, (TILE_PATTERN_TABLE)
    .loopReading:
		ld a, (de)
		cp $ff
		jp z, .end
		cp 0
		jp z, .checkNext
		
		;; How many to skip		
		call .skipRepeats
		
	.checkNext:
		inc de
	
		;; How many to include?
		ld a, (de)
		cp 0
		jp z, .afterLooping
	.loopSingleAddition:
		ld (hl), c
		inc hl
		ld (hl), b
		inc hl
		
		;; TODO: MAKE THIS SMARTER! Too tired now.
		inc bc
		inc bc
		inc bc
		inc bc
		inc bc
		inc bc
		inc bc
		inc bc
		inc bc
		
		dec a
		jp nz, .loopSingleAddition		
	.afterLooping:
		inc de
		jp .loopReading
	.end:
		pop hl
		pop bc
		ret
		
	.skipRepeats:
		push de
		push hl
		ld h, b
		ld l, c
		ld b, a
		ld de, 9
	.stupidLoop:
		add hl, de
		djnz .stupidLoop
		ld b, h
		ld c, l
		
		pop hl
		pop de
		ret

UnpackColourTable:
		push bc
		push de
		push hl
		
		ld hl, TEXT_BUFFER
		ld b, 14 * 14 + 2
	.loopEntries:
		push hl
		ld e, (hl)
		inc hl
		ld d, (hl)
		
		ld hl, 8
		add hl, de
		ld e, (hl) ;; E now contains the palette index.
		ld d, 0
		ld hl, (TILE_COLOUR_TABLE)
		ex de, hl
		add hl, hl
		add hl, hl
		add hl, hl 
		add hl, de ;; HL has now the start of the palette.

		pop de ;; HL before adding.
		ld a, l
		ld (de), a
		inc de
		ld a, h
		ld (de), a
		inc de
		ex de, hl
		djnz .loopEntries
		pop bc
		pop de
		pop hl
		ret


LoadRLE2VRAM:
	;; Unpack RLE-encoded data to VRAM.
	;; Pairs of [len][value] entries;
	;; ends when len=0.
	;; Used just to display something like the full screens (such as the title
	;; screen)
  .loop:	
	ld a, (de) ;; Count
	and a
	ret z
	ld c, a
	ld b, 0
	inc de
	ld a, (de) ;; Colour.
	inc de
	push de
	push bc
	push hl
	call FILVRM
	pop hl
	pop bc
	pop de
	add hl, bc
	jp .loop

ClearUI:
	ld de, UIGFX_EMPTY_SCREEN_RLE
	ld hl, $1800
	call LoadRLE2VRAM
	ret	
		