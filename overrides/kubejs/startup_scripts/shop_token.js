StartupEvents.registry('item', event => {
    event.create('shop_token')
        .displayName('Shop Expansion Token')
        .maxStackSize(64)
        .glow(true)
})