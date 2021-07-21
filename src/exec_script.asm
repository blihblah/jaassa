;;;
; Routines to execute the scripts.
;

ExecuteScriptHL:
		;; Script address is in HL.
	
	.nextCommand:
		ld a, (hl)
		inc hl
		and a
		jp z, .cmdEnd
		dec a
		jp z, .cmdGoto
		dec a
		jp z, .cmdSetItemLoc
		dec a
		jp z, .cmdText
		dec a
		jp z, .cmdIfTrue
		dec a
		jp z, .cmdSet
		dec a
		jp z, .cmdIsLoc
		dec a
		jp z, .cmdIsState
		dec a
		jp z, .cmdSetTile
		dec a
		jp z, .cmdGoEnd
		dec a
		jp z, .cmdTextEnd
		dec a
		jp z, .cmdTake
		dec a
		jp z, .cmdTakeEnd
		dec a
		jp z, .cmdIsObject
		dec a
		jp z, .cmdDisplayLocationDescEnd
		dec a
		jp z, .cmdWaitForFire
		dec a
		jp z, .cmdJump
		dec a
		jp z, .cmdIsStateLEQ
		dec a
		jp z, .cmdFinishGame
		;; TODO: Add "CALL <routine handle>"
		;; TODO: Add "IsItemLoc <item> <location>"
		;; TODO: Implement SetTile
		ret
		
	.cmdEnd:
		ret
	.cmdGoto:
		push hl
		call .movePlayer
		jp .popPassTwo
	.cmdSetItemLoc:
		push hl ;;
		call UnrefHL ;; Now has item ROM address.
		inc hl
		inc hl 
		call UnrefHL ;; Now has item RAM address.
		ex de, hl
		pop hl
		inc hl
		inc hl ;; Now points to new location
		ld c, (hl)
		inc hl
		ld b, (hl)
		inc hl
		ld a, c
		ld (de), a
		inc de
		ld a, b
		ld (de), a
		
		jp .nextCommand
	.cmdText:
		push hl
		call UnrefHL
		call DisplayTextHL
		jp .popPassTwo
	.cmdIfTrue:
		push hl
		;ld e, (hl)
		;ld d, 0
		ld hl, GAME_STATE
		;add hl, de
		ld a, (hl)
		and a
		jp z, .popPassTwo
		pop hl
		call UnrefHL
		jp .nextCommand
	.cmdSet:
		push hl
		;inc hl
		ld e, (hl)
		inc hl
		ld a, (hl)
		ld d, 0
		ld hl, GAME_STATE
		add hl, de
		ld (hl), a
		jp .popPassTwo
	.cmdIsLoc:
		push hl
		ld a, 0
		ld (GAME_STATE), a
		call UnrefHL
		ld de, (PLAYER_LOCATION)
		ld a, h
		xor d
		jp nz, .popPassTwo
		ld a, l
		xor e
		jp nz, .popPassTwo
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassTwo
		
	.cmdIsState:
		xor a
		ld (GAME_STATE), a
		push hl
		ld e, (hl)
		inc hl
		ld b, (hl)
		ld d, 0
		ld hl, GAME_STATE
		add hl, de
		ld a, (hl)
		cp b
		jp nz, .popPassTwo
		ld a, 1
		ld (GAME_STATE), a		
		jp .popPassTwo
		
	.cmdSetTile:
		; TODO!
		jp .popPassTwo
	.cmdGoEnd:
		call .movePlayer
		ret
	.cmdTextEnd:
		call UnrefHL
		call DisplayTextHL
		ret
	.cmdTake:
		push hl
		call UnrefHL
		inc hl
		inc hl
		call UnrefHL
		ld de, C_PLAYER_INVENTORY
		ld (hl), e
		inc hl
		ld (hl), d
		jp .popPassTwo
	
	.cmdTakeEnd:
		call UnrefHL
		inc hl
		inc hl
		call UnrefHL
		ld de, C_PLAYER_INVENTORY
		ld (hl), e
		inc hl
		ld (hl), d
		ret
		
	.cmdIsObject:
		;; Three values.
		;; object type (item, B), object addr (W)
		;; object type (dir, B), direction (B), empty (B)
		ld a, 0
		ld (GAME_STATE), a
		ld a, (OBJECT_ADDR)
		ld b, (hl)
		inc hl
		push hl
		;cp b
		;jp nz, .popPassTwo
		cp C_ITEM_DIRECTION
		jp z, .isObjectDirection
		; Comparing items.
		ld a, (OBJECT_ADDR + 1)
		ld b, (hl)
		xor b		
		jp nz, .popPassTwo
		ld a, (OBJECT_ADDR + 2)
		inc hl
		ld b, (hl)
		jp nz, .popPassTwo
	.isTrue:
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassTwo
	
	.isObjectDirection:
		ld a, (OBJECT_ADDR + 1)
		ld b, (hl)
		cp b
		jp nz, .popPassTwo
		jp .isTrue
	
	
	.cmdDisplayLocationDescEnd:
		push hl
		call RenderLocationDescription
		pop hl
		ret
		
	.cmdWaitForFire:
		push hl
		call WaitForFireButton
		pop hl
		jp .nextCommand

	.cmdJump:
		call UnrefHL
		jp .nextCommand

	.cmdIsStateLEQ:
		xor a
		ld (GAME_STATE), a
		push hl
		ld e, (hl)
		inc hl
		ld b, (hl)
		ld d, 0
		ld hl, GAME_STATE
		add hl, de
		ld a, (hl)
		cp b
		jp nc, .popPassTwo
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassTwo

	.cmdFinishGame:
	    jp InitStack

	.popPassTwo:
		;; Typical ending for the script: pop the code execution pointer
		;; back to HL and increment it by 2 bytes
		pop hl
		inc hl
		inc hl
		jp .nextCommand
		
		
	.movePlayer:
		;; Moves the player to another location and calls the related routines.
		call UnrefHL
		ld (PLAYER_LOCATION), hl	
		call RenderLocationViewport
		call ScanLocationHotspots
		call ExecuteLocationScript
		ret
		
		
		
		