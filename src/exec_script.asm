;;;
; Routines to execute the scripts.
;

ExecuteScriptHL:
		;; Script address is in HL.
	;ld a, (CURRENT_PAGE)
	;ld (CURRENT_SCRIPT_PAGE), a
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
		dec a
		jp z, .cmdPlaySound
		;; TODO: Add "CALL <routine handle>"
		;; TODO: Add "IsItemLoc <item> <location>"
		;; TODO: Implement SetTile
		ret
    .backToMyPage:
        ld a, (CURRENT_SCRIPT_PAGE)
        call SwapCode
        ret
		
	.cmdEnd:
		ret
	.cmdGoto:
		push hl
		call .movePlayer
		jp .popPassTwo
	.cmdSetItemLoc:
		push hl ;;
		call UnrefPageHL ;; Now has item ROM address.
		inc hl ;; Past item name address.
		inc hl
		inc hl 
		call UnrefHL ;; Now has item RAM address.
		call .backToMyPage
		ex de, hl
		pop hl
		inc hl ;; Past item page
		inc hl
		inc hl ;; Now points to new location

		;; Copy the three bytes' address.
		ld bc, 3
		ldir
		jp .nextCommand
	.cmdText:
		push hl
		call UnrefPageHL
		call DisplayTextHL
		call .backToMyPage
		jp .popPassThree
	.cmdIfTrue:
		push hl
		ld hl, GAME_STATE
		ld a, (hl)
		and a
		jp z, .popPassThree
		pop hl
		ld a, (hl)
		ld (CURRENT_SCRIPT_PAGE), a
		call UnrefPageHL
		jp ExecuteScriptHL
	.cmdSet:
		push hl
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
		ld a, (HL)
		ld e, a
		ld a, (PLAYER_LOCATION_PAGE)
		xor e
		jp nz, .popPassThree

		inc hl
		call UnrefHL

		ld de, (PLAYER_LOCATION)
		ld a, h
		xor d
		jp nz, .popPassThree
		ld a, l
		xor e
		jp nz, .popPassThree
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassThree
		
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
		call UnrefPageHL
		call DisplayTextHL
		;; We don't need to return to the script's page.
		ret
	.cmdTake:
		push hl
		call UnrefPageHL
		inc hl
		inc hl
		inc hl
		call UnrefHL
		;; Set the player page.
		ld a, 0
		ld (hl), a
		inc hl
		ld de, C_PLAYER_INVENTORY
		ld (hl), e
		inc hl
		ld (hl), d
		call .backToMyPage
		jp .popPassThree
	
	.cmdTakeEnd:
		call UnrefPageHL
		inc hl
		inc hl
		inc hl
		call UnrefHL
		ld a, 0
		ld (hl), a
		inc hl
		ld de, C_PLAYER_INVENTORY
		ld (hl), e
		inc hl
		ld (hl), d
		call .backToMyPage
		ret
		
	.cmdIsObject:
		;; Four values.
		;; object type (item, B), item page (B), object addr (W)
		;; object type (dir, B), direction (B), empty (W)
		;; TODO: Finish conversion!
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
		jp nz, .popPassThree
		ld a, (OBJECT_ADDR + 2)
		inc hl
		ld b, (hl)
		xor b
		jp nz, .popPassThree
		ld a, (OBJECT_ADDR + 3)
		inc hl
		ld b, (hl)
		xor b
		jp nz, .popPassThree
	.isTrue:
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassThree
	
	.isObjectDirection:
		ld a, (OBJECT_ADDR + 1)
		ld b, (hl)
		cp b
		jp nz, .popPassThree
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
	    ld a, (hl)
	    ld (CURRENT_SCRIPT_PAGE), a
		call UnrefPageHL

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
		inc b
		cp b
		jp nc, .popPassTwo
		ld a, 1
		ld (GAME_STATE), a
		jp .popPassTwo

	.cmdFinishGame:
	    jp InitStack

	.cmdPlaySound:
	    push hl
	    ld e, (hl)
	    inc hl
	    ld d, (hl)
	    call PlaySound
	    jp .popPassTwo

	.popPassThree:
	    ;; Typical ending for the script: pop the execution pointer back to HL
	    ;; and increment it by 3 bytes (page + two-byte parameter)
		pop hl
		inc hl
		inc hl
		inc hl
		jp .nextCommand

	.popPassTwo:
		;; Typical ending for the script: pop the code execution pointer
		;; back to HL and increment it by 2 bytes, i.e., two-byte parameter
		pop hl
		inc hl
		inc hl
		jp .nextCommand
		
		
	.movePlayer:
		;; Moves the player to another location and calls the related routines.
		call UnrefPageHL
		ld (PLAYER_LOCATION_PAGE), a
		ld (PLAYER_LOCATION), hl
		call SwapCode
		call RenderLocationViewport
		call ScanLocationHotspots
		call ExecuteLocationScript
		ret
		
		
		
		