# Notes on diffbot

These notes detail the Custom API changes for UK targets, and any other challenges.

## Exporting rules

    import requests
    r = requests.get('https://api.diffbot.com/v3/custom?token={token}'.format(token=settings.DIFFBOT_TOKEN))
    jrules = r.json()

## Importing rules

    with open('/path/to/rules.json', 'r') as f:
        jrules = json.loads(f.read())
        import requests
        requests.post('https://api.diffbot.com/v3/custom?token={token}'.format(token=settings.DIFFBOT_TOKEN),
                      json=jrules)

See https://www.diffbot.com/dev/docs/custom/managing/

## Offspring

    sizes: select#sizeShoe option
    colourway: .productColour

## Schuh

    sizes: #sizes option
    title: #itemTitle h1
    brand: .brandName

## Footasylum

Support patched something, and now it can grab price too.

    sizes: div.sizedrops span.inline-block:contains(Size)

## Sportsdirect

Needs custom cookie sent via `{'X-Forward-Cookie': 'ChosenSite=www; SportsDirect_AnonymousUserCurrency=GBP;'}`.
This ensures GBP prices.

    sizes: .sizeButtons a
    colourway: span[id$=colourName]

## Vans

    sizes: select#attr-size option
    colourway: .product-content-form-attr-selected

## New balance

    sizes: ul[data-attr=size] li span:not(:contains(EU))
    title: section.product-info > div.row > div.columns:first-of-type  h1
    colourway: section.product-info div[style*=block].selected-color > div.insert

## Timberland

    sizes: .attr-size label
    offerPrice: meta[og:price:amount]

## Adidas

    sizes: div[data-auto-id=size-selector] select option
    title: .product_category___2txJk .subtitle___2Km_d, .product_information_title___3W4Bd 
    
## Urban outfitters

    sizes: .c-product-sizes__ul label
    
## Fight club

Need to force currency with Cookie: `{'X-Forward-Cookie': 'currency=GBP;'}`.

    sizes: .hidden-element button
    colourway: .product-attribute-list li:eq(2)
    
## Urban Industry

    sizes: .choices-eh label
    offerPrice: p.currentprice span.money  

and also attribute filter for `offerPrice`, `data-currency-gbp`.

## Nike

Currently this is not working with Diffbot, the price seems to load even without javascript
so it's odd they can't scrape it. The custom API preview window just 500s out, and any attempt
at adding a custom filter doesn't seem to work, I tried `div[data-test=product-price]` for the `offerPrice`
and `input[for=skuAndSize]` for size inputs, but to no avail.

Waiting on support.

# Footpatrol

This website appears to be in pre-open status. Even in my browser sometimes I get pushed into a queue before
I can view it, and Diffbot just times out.


## Footlocker

The images are loaded by "scene7", and with XPATH can be found with `//div[@class="s7thumb"][@data-namespace="s7classic"]/@style` and then parsing out the "background-url".

I tried to at least get the style attribute with diffbot using the selector div.s7thumb div[data-namespace=s7classic] and then adding the Attribute filter "style", but again nothing at all is returned.
