"""Baserow table and field IDs for the Game Tracker database (id=339).
Provisioned via a one-off script; see README for how to regenerate if the schema changes."""

TABLE_GAMES = 1374
TABLE_COPIES = 1375
TABLE_SALES = 1376

# Games (1374)
G_TITLE = "field_14833"
G_PLATFORM = "field_14842"
G_TARGET = "field_14843"
G_UPGRADE_TO = "field_14844"
# Per-condition prices (Number, 2 decimals). "CIB Price" was originally named
# "Market price".
G_CIB_PRICE = "field_14845"  # "CIB Price" -- complete in box
G_LOOSE_PRICE = "field_14877"  # "Loose Price" -- disc only
G_BOX_ONLY_PRICE = "field_14878"  # "Box Only Price" -- case + artwork, no disc
G_SEALED_PRICE = "field_14879"  # "Sealed Price" -- new / factory sealed
G_MANUAL_ONLY_PRICE = "field_14880"  # "Manual Only Price"
G_NOTES = "field_14846"
G_CIB_REQUIRES = "field_14864"
G_UPC = "field_14872"
G_COVER_URL = "field_14873"  # "Cover URL" (URL)
G_PRICE_UPDATED = "field_14874"  # "Price updated" (Date, no time) -- set whenever any price changes
G_COMPLETIONATOR_URL = "field_14875"  # "Completionator URL" (URL) -- filled by scripts/import_completionator.py

PLATFORM_OPTIONS = {
    "OG Xbox": 3859,
    "Xbox 360": 3860,
    "Xbox One": 3861,
    "Xbox Series X|S": 3862,
}
PLATFORM_OPTIONS_BY_ID = {v: k for k, v in PLATFORM_OPTIONS.items()}

CIB_COMPONENT_OPTIONS = {"Disc": 3875, "Case": 3876, "Manual": 3877}
CIB_COMPONENT_OPTIONS_BY_ID = {v: k for k, v in CIB_COMPONENT_OPTIONS.items()}

# Copies (1375)
C_COPY_ID = "field_14836"
C_GAME = "field_14847"
C_STATUS = "field_14849"
C_PURCHASE_PRICE = "field_14851"
C_PURCHASE_DATE = "field_14852"
C_PURCHASED_FROM = "field_14853"
C_LOCATION = "field_14854"
C_NOTES = "field_14855"
C_SEALED = "field_14871"
C_HAS_DISC = "field_14865"
C_DISC_QUALITY = "field_14866"
C_HAS_CASE = "field_14867"
C_CASE_QUALITY = "field_14868"
C_HAS_MANUAL = "field_14869"
C_MANUAL_QUALITY = "field_14870"
C_PHOTO = "field_14876"  # "Photo" (File)

STATUS_OPTIONS = {"Collection": 3863, "For Sale": 3864, "Sold": 3865}
STATUS_OPTIONS_BY_ID = {v: k for k, v in STATUS_OPTIONS.items()}

# Sales (1376)
S_SALE_ID = "field_14839"
S_COPY = "field_14856"
S_SOLD_ON = "field_14858"
S_SALE_DATE = "field_14859"
S_SALE_PRICE = "field_14860"
S_FEES = "field_14861"
S_SHIPPING_COST = "field_14862"
S_NET = "field_14863"

SOLD_ON_OPTIONS = {
    "eBay": 3870,
    "Mercari": 3871,
    "Facebook Marketplace": 3872,
    "Local": 3873,
    "Other": 3874,
}
SOLD_ON_OPTIONS_BY_ID = {v: k for k, v in SOLD_ON_OPTIONS.items()}
