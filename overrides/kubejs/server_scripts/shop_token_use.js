ItemEvents.rightClicked(event => {
    if (event.item.id == 'kubejs:shop_token') {

        event.player.tell('Shop Token Redeemed!')

        event.player.runCommand(
            'ftbteams parties extra_claim_chunks ' +
            event.player.username +
            ' add 15'
        )

        event.item.count--
    }
})