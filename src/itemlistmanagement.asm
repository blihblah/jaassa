;; Routines to handle the hotspot list management.
;; Hotspots are directions, local items and inventory items.

;; Regenerate the list of hotspots at the current location.
;; This includes directions in which to move.		
ScanLocationHotspots:
		xor a
		ld (VIEW_ITEM_CHOSEN), a
		ld (VIEW_ITEM_LENGTH), a
		ld (VIEW_ITEM_OFFSET), a
		call UpdatePlayerLocation
		
		;; Scan directions.
		ld hl, (PLAYER_LOCATION_DIRECTIONS)
		ld b, (hl)
		ld a, b
		cp 0
		jp z, .pastDirections
		ld c, -1
		
	.decreaseList:
		inc hl
		ld a, (hl) ;; Direction code
		inc hl ;; Command code 
		inc hl ;; Script pointer byte 1
		inc hl ;; Script pointer byte 2
		cp c
		jp z, .directionEntryProcessed ;; If duplicate direction, ignore.
		ld c, a

		push hl
		ld (ADD_TO_VIEW_LIST + 1), a
		ld a, C_ITEM_DIRECTION
		ld (ADD_TO_VIEW_LIST), a
		call AddItemToList
		pop hl		
	.directionEntryProcessed:
		djnz .decreaseList
		
	.pastDirections:
		;; Go through all items, find the ones that are here.
		
		ld hl, PLAYER_LOCATION
		ld e, (hl)
		inc hl
		ld d, (hl)
		ex de, hl		
		ld (LOOPVARS2), hl
		ld a, C_ITEM_LOCAL_ICON
		ld (ADD_TO_VIEW_LIST), a
		call .findItemsAtAddress
		
		ld hl, C_PLAYER_INVENTORY
		ld (LOOPVARS2), hl
		ld a, C_ITEM_INVENTORY_ICON
		ld (ADD_TO_VIEW_LIST), a
		call .findItemsAtAddress
		ret
				
	.findItemsAtAddress:
		ld hl, (ITEM_ADDRESS_LIST)
		ld b, (hl)
		inc hl
		
	.loopItems:
		ld e, (hl)
		inc hl
		ld d, (hl)
		inc hl
		push hl ;; Put next item to wait in the stack.
		;; DE has the address of the item record.
		push de
		pop ix
		ld d, (ix + 3)
		ld e, (ix + 2)
		;; DE has now the RAM address.
		push de
		pop iy
		ld d, (iy + 1)
		ld e, (iy)
		ld a, (LOOPVARS2)
		cp e
		jp nz, .notHere
		ld a, (LOOPVARS2 + 1)
		cp d
		jp nz, .notHere
		
		;; Item was here.
		;ld a, (ix + 1)
		ld a, ixh
		ld (ADD_TO_VIEW_LIST + 2), a
		;ld a, (ix)
		ld a, ixl
		ld (ADD_TO_VIEW_LIST + 1), a
		call AddItemToList
	.notHere:
		pop hl
		djnz .loopItems
		ret
		

AddItemToList:
		push bc
		ld a, (VIEW_ITEM_LENGTH)
		ld e, a
		rlca
		add a, e ;; Multiplied by 3
		ld d, 0
		ld e, a
		ld hl, VIEW_ITEM_LIST
		add hl, de
		ld a, (ADD_TO_VIEW_LIST)
		ld (hl), a
		inc hl
		ld a, (ADD_TO_VIEW_LIST + 1)
		ld (hl), a
		inc hl
		ld a, (ADD_TO_VIEW_LIST + 2)
		ld (hl), a

		ld hl, VIEW_ITEM_LENGTH
		inc (hl)
		pop bc
		ret


RefreshViewItemList:
		call ClearInventoryBox
		ld de, $1800 + 32 + 17 + 32 + 1
		ld (LOOPVARS), de

		ld a, (VIEW_ITEM_OFFSET)
		ld c, a
		ld a, (VIEW_ITEM_LENGTH)
		sub c
		cp C_VISIBLE_LIST_LENGTH
		jp c, .onlyRemainder
		ld a, C_VISIBLE_LIST_LENGTH

	.onlyRemainder:
		ld b, a ;; How many items are left to handle.
		ld a, c
		;; Mul A by 3 to get the offset in list.
		rlca
		add a, c
		ld e, a
		ld d, 0
		ld hl, VIEW_ITEM_LIST
		add hl, de ;; Now points to the first item to render.

	.nextItem:
		push hl
		push bc
		ld a, (hl)
		push hl
		ld hl, (LOOPVARS) ;; VRAM addy
		call WRTVRM
		ld hl, (LOOPVARS)
		inc hl
		ld (LOOPVARS), hl		
		
		pop hl
		ld a, (hl)
		inc hl
		
		cp C_ITEM_DIRECTION ;; If 0, it is a direction.
		jp z, .isDirection
	.isObject:
		;; Data points to item record address.
		
		ld e, (hl)
		inc hl
		ld d, (hl)
		ex de, hl
		
		call UnrefHL
		;; DE has the item record address now.
		ld (LOOPVARS2), hl
		;; That is also the name of the item.
		jp .wrapUp

	
	.isDirection:
	    ;; Data points to direction index.
		ld a, (hl)
		ld hl, DIRECTION_NAMES
		rlca
		ld e, a
		ld d, 0
		add hl, de
		;; HL now points the direction name address.
		ld e, (hl)
		inc hl
		ld d, (hl)
		ld (LOOPVARS2), de
		ld de, (LOOPVARS) ;; VRAM address
		ex de, hl

		;; Now, uncompress the text.
	.wrapUp:
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
		djnz .nextItem
	ret