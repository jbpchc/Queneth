"""Static seed content: taxonomy, fictional boutiques and houses, palette,
product templates and a hand-written perfume library. Every name is invented;
no real luxury brand appears anywhere (spec §2)."""

from dataclasses import dataclass, field

from app.core.palette import PALETTE  # noqa: F401 — re-exported for the seed

CATEGORIES: list[tuple[str, str, str, list[str]]] = [
    ("clothing", "Clothing", "Cut, cloth and the way it moves.",
     ["Dresses", "Tops", "Outerwear", "Trousers", "Knitwear", "Suiting"]),
    ("shoes", "Shoes", "Lasts worth knowing by name.",
     ["Heels", "Sneakers", "Loafers", "Boots", "Sandals"]),
    ("bags", "Bags", "Hardware, structure, and what fits inside.",
     ["Totes", "Shoulder", "Crossbody", "Clutches", "Backpacks"]),
    ("accessories", "Accessories", "Finishing details, finely made.",
     ["Jewelry", "Watches", "Sunglasses", "Belts", "Scarves", "Hats"]),
    ("perfumes", "Perfumes", "Notes, sillage, and the memory they leave.",
     ["Women", "Men", "Unisex", "Niche", "Gift sets"]),
]  # fmt: skip


QUIET_COLORS = {"Ivory", "Camel", "Sand", "Noir", "Ecru", "Chocolate", "Navy"}
NIGHT_COLORS = {"Noir", "Bordeaux", "Gold", "Navy", "Chocolate"}


@dataclass(frozen=True)
class Boutique:
    slug: str
    name: str
    owner_email: str
    owner_name: str
    city: str
    tagline: str
    bio: str
    color: str
    initials: str
    banner_shape: str
    brands: tuple[str, ...]
    specialties: tuple[str, ...]
    featured: bool = False


RETURN_POLICY = (
    "Returns accepted within 7 days of delivery for unworn pieces with tags attached. "
    "Fragrances can be returned sealed. Refunds go back to your QueWallet once we receive the item."
)

BOUTIQUES: list[Boutique] = [
    Boutique("atelier-lumen", "Atelier Lumen", "seller@queneth.test", "Atelier Lumen", "Manila",
             "Quiet luxury, cut in Manila.",
             "Atelier Lumen makes pared-back wardrobes in natural fibers: bias-cut silks, honest cottons, "
             "and knits that soften with every wear. Every piece is cut and finished in our Ermita studio.",
             "b08457", "AL", "dress", ("Lumen Atelier", "Halden Studio"),
             ("dresses", "tops", "knitwear", "scarves"), True),
    Boutique("maison-verde", "Maison Verdé", "verde@queneth.test", "Maison Verdé", "Cebu",
             "Tailoring with a coastal ease.",
             "Maison Verdé brings Savile Row discipline to island weather: half-canvassed jackets, "
             "breathable wool-linen, and trousers with a clean break.",
             "6b6b3a", "MV", "blazer", ("Maison Verdé", "Anvers & Co."),
             ("outerwear", "suiting", "trousers", "belts"), True),
    Boutique("sable-and-thread", "Sable & Thread", "sable@queneth.test", "Sable & Thread", "Makati",
             "Knitwear that keeps its shape.",
             "A knit studio obsessed with gauge and hand-feel. We source cashmere and merino from "
             "certified mills and finish every seam by hand-linking.",
             "e8b4b8", "S&T", "knit", ("Sable & Thread", "Kaia Knits"),
             ("knitwear", "scarves", "hats", "tops")),
    Boutique("nocturne-parfums", "Nocturne Parfums", "nocturne@queneth.test", "Nocturne Parfums", "Taguig",
             "Niche perfumery after dark.",
             "Nocturne composes small-batch fragrances around Philippine botanicals: sampaguita, "
             "calamansi, pili and ylang-ylang, macerated for weeks before bottling.",
             "1f2a44", "N", "perfume-1", ("Nocturne", "Ylang Mer Parfums"),
             ("women", "men", "unisex", "niche", "gift-sets"), True),
    Boutique("casa-ilaya", "Casa Ilaya", "ilaya@queneth.test", "Casa Ilaya", "Iloilo",
             "Hand-woven, sun-ready.",
             "Casa Ilaya works with weaving communities in Panay on abaca, piña and raffia pieces: "
             "market totes, espadrilles and wide-brim hats made for the tropics.",
             "d9c49b", "CI", "tote", ("Casa Ilaya", "Tala Weaving Co."),
             ("sandals", "totes", "hats", "clutches")),
    Boutique("obra-leather", "Obra Leather", "obra@queneth.test", "Obra Leather", "Marikina",
             "Marikina lasts, Goodyear welted.",
             "Three generations of Marikina shoemaking. Obra builds on its own lasts with vegetable-tanned "
             "leather, stitched welts and soles you can resole for decades.",
             "4b2e24", "OL", "boots", ("Obra", "Calle Marikina"),
             ("heels", "sneakers", "loafers", "boots", "belts", "backpacks"), True),
    Boutique("kintsu-jewels", "Kintsu Jewels", "kintsu@queneth.test", "Kintsu Jewels", "Davao",
             "Gold, mended beautifully.",
             "Kintsu sets South Sea pearls and recycled gold in pieces inspired by kintsugi: the beauty "
             "of repair. Watches are assembled with Swiss-made movements.",
             "c9a44c", "K", "necklace", ("Kintsu", "Orel & Pine"),
             ("jewelry", "watches")),
    Boutique("rue-solenne", "Rue Solenne", "solenne@queneth.test", "Rue Solenne", "Baguio",
             "Parisian line, mountain light.",
             "Rue Solenne edits structured leather bags, acetate eyewear and a small fragrance wardrobe, "
             "all designed between Baguio and the Marais.",
             "6b1e2e", "RS", "shoulder", ("Rue Solenne", "Solenne Optique"),
             ("sunglasses", "shoulder", "crossbody", "clutches", "niche", "unisex")),
]  # fmt: skip

REVIEWERS: list[tuple[str, str]] = [
    ("buyer@queneth.test", "Isabela Reyes"),
    ("collector@queneth.test", "Marco Villanueva"),
    ("ana@queneth.test", "Ana Santos"),
    ("rafael@queneth.test", "Rafael Domingo"),
    ("bea@queneth.test", "Bea Lim"),
    ("mika@queneth.test", "Mika Tan"),
    ("jo@queneth.test", "Jo Aquino"),
    ("lia@queneth.test", "Lia Navarro"),
]


@dataclass(frozen=True)
class Template:
    names: tuple[str, ...]
    materials: tuple[str, ...]
    colors: tuple[str, ...]
    price: tuple[int, int]
    extra_tags: tuple[str, ...] = field(default_factory=tuple)


TEMPLATES: dict[str, Template] = {
    "dresses": Template(("Bias-Cut Slip Dress", "Column Gown", "Wrap Midi Dress", "Pleated Shirt Dress", "Draped Jersey Dress"),
                        ("Silk", "Crepe", "Linen", "Satin", "Jersey"), ("Ivory", "Noir", "Bordeaux", "Sage", "Camel", "Blush"), (6800, 28500)),
    "tops": Template(("Poplin Shirt", "Cowl-Neck Camisole", "Boat-Neck Tee", "Pintuck Blouse", "Ribbed Tank"),
                     ("Cotton", "Silk", "Linen", "Modal", "Cotton"), ("Ivory", "Ecru", "Noir", "Blush", "Navy"), (3200, 12500)),
    "outerwear": Template(("Double-Faced Wrap Coat", "Trench Coat", "Cropped Bouclé Jacket", "Car Coat", "Quilted Liner Jacket"),
                          ("Wool", "Cotton Gabardine", "Bouclé", "Wool-Cashmere", "Nylon"), ("Camel", "Noir", "Sand", "Olive", "Navy"), (14500, 48000)),
    "trousers": Template(("Wide-Leg Trousers", "Pleated Tapered Trousers", "Straight Selvedge Jeans", "Drawstring Linen Trousers", "Cigarette Pants"),
                         ("Wool", "Wool", "Denim", "Linen", "Crepe"), ("Noir", "Sand", "Navy", "Ecru", "Olive"), (4800, 14500)),
    "knitwear": Template(("Cashmere Crewneck", "Cable Cardigan", "Fine-Gauge Polo", "Ribbed Turtleneck", "Mohair Vest"),
                         ("Cashmere", "Merino", "Merino", "Cashmere", "Mohair"), ("Camel", "Ecru", "Noir", "Blush", "Sage", "Lilac"), (5800, 22000)),
    "suiting": Template(("Single-Breasted Blazer", "Double-Breasted Blazer", "Tuxedo Jacket", "Waistcoat", "Unstructured Linen Blazer"),
                        ("Wool", "Wool", "Grain de Poudre", "Wool", "Linen"), ("Navy", "Noir", "Sand", "Olive", "Camel"), (12500, 42000)),
    "heels": Template(("Pointed Pump", "Slingback Kitten Heel", "Strappy Sandal Heel", "Sculpted Mule", "Block-Heel Mary Jane"),
                      ("Calf Leather", "Patent Leather", "Nappa", "Suede", "Calf Leather"), ("Noir", "Blush", "Bordeaux", "Sand", "Ivory"), (7800, 26500)),
    "sneakers": Template(("Court Sneaker", "Suede Runner", "Canvas Low-Top", "Leather High-Top", "Knit Trainer"),
                         ("Calf Leather", "Suede", "Canvas", "Calf Leather", "Recycled Knit"), ("Ivory", "Noir", "Sand", "Navy", "Sage"), (6500, 18500)),
    "loafers": Template(("Penny Loafer", "Tassel Loafer", "Lug-Sole Loafer", "Driving Moccasin", "Velvet Slipper"),
                        ("Calf Leather", "Suede", "Brushed Leather", "Nubuck", "Velvet"), ("Chocolate", "Noir", "Bordeaux", "Camel"), (8500, 22500)),
    "boots": Template(("Chelsea Boot", "Knee-High Riding Boot", "Lace-Up Ankle Boot", "Western Boot", "Shearling-Lined Boot"),
                      ("Calf Leather", "Calf Leather", "Suede", "Embossed Leather", "Suede"), ("Noir", "Chocolate", "Camel", "Bordeaux"), (12800, 34500)),
    "sandals": Template(("Woven Slide", "Abaca Espadrille", "Thong Sandal", "Fisherman Sandal", "Ankle-Tie Flat"),
                        ("Raffia", "Abaca", "Vachetta", "Calf Leather", "Canvas"), ("Natural", "Sand", "Terracotta", "Noir", "Citron"), (3800, 14500), ("citrus-sun",)),
    "totes": Template(("Structured Tote", "Woven Market Tote", "East-West Tote", "Soft Shopper", "Canvas Book Tote"),
                      ("Grained Leather", "Abaca", "Calf Leather", "Nappa", "Waxed Canvas"), ("Camel", "Natural", "Noir", "Sand", "Olive"), (9800, 48000)),
    "shoulder": Template(("Saddle Bag", "Half-Moon Bag", "Pleated Pouch Bag", "Top-Handle Bag", "Chain Shoulder Bag"),
                         ("Box Calf", "Grained Leather", "Nappa", "Box Calf", "Quilted Lambskin"), ("Bordeaux", "Noir", "Camel", "Blush", "Sage"), (14500, 88000)),
    "crossbody": Template(("Camera Bag", "Phone Pouch", "Box Crossbody", "Saddle Crossbody", "Messenger"),
                          ("Grained Leather", "Nappa", "Box Calf", "Suede", "Waxed Canvas"), ("Noir", "Cobalt", "Camel", "Bordeaux"), (8500, 38000)),
    "clutches": Template(("Envelope Clutch", "Minaudière", "Knot Clutch", "Piña Pleated Clutch", "Frame Clutch"),
                         ("Satin", "Brass", "Nappa", "Piña Silk", "Velvet"), ("Noir", "Gold", "Ivory", "Bordeaux"), (6500, 32000), ("after-hours",)),
    "backpacks": Template(("Leather Backpack", "Drawstring Backpack", "Mini Backpack", "Roll-Top Backpack"),
                          ("Vegetable-Tanned Leather", "Nappa", "Grained Leather", "Waxed Canvas"), ("Chocolate", "Noir", "Olive"), (9800, 36000)),
    "jewelry": Template(("Pearl Drop Earrings", "Signet Ring", "Herringbone Chain", "Tennis Bracelet", "Hoop Earrings"),
                        ("18k Gold Vermeil", "Recycled 18k Gold", "Gold Vermeil", "Sterling Silver", "Recycled 18k Gold"), ("Gold", "Rose Gold", "Silver"), (2800, 64000)),
    "watches": Template(("Automatic Dress Watch", "Chronograph", "Tank-Style Watch", "Dive Watch"),
                        ("Stainless Steel", "Stainless Steel", "Gold-Plated Steel", "Titanium"), ("Silver", "Gold", "Noir"), (18500, 145000)),
    "sunglasses": Template(("Cat-Eye Sunglasses", "Aviator Sunglasses", "Square Acetate Sunglasses", "Round Wire Sunglasses"),
                           ("Italian Acetate", "Titanium", "Italian Acetate", "Titanium"), ("Tortoise", "Noir", "Gold", "Bordeaux"), (4800, 16500), ("citrus-sun",)),
    "belts": Template(("Reversible Belt", "Woven Leather Belt", "Skinny Buckle Belt", "Chain Belt"),
                      ("Calf Leather", "Braided Leather", "Calf Leather", "Brass"), ("Noir", "Chocolate", "Camel", "Gold"), (2800, 9800)),
    "scarves": Template(("Silk Twill Square", "Cashmere Stole", "Piña Silk Scarf", "Printed Bandana"),
                        ("Silk Twill", "Cashmere", "Piña Silk", "Cotton Voile"), ("Bordeaux", "Camel", "Ivory", "Cobalt", "Terracotta"), (2400, 12800)),
    "hats": Template(("Panama Hat", "Wool Fedora", "Raffia Bucket Hat", "Cashmere Beanie"),
                     ("Toquilla Straw", "Wool Felt", "Raffia", "Cashmere"), ("Natural", "Noir", "Sand", "Camel"), (2200, 8800)),
}  # fmt: skip


@dataclass(frozen=True)
class Perfume:
    name: str
    sub: str
    boutique: str
    family: str
    concentration: str
    top: tuple[str, ...]
    heart: tuple[str, ...]
    base: tuple[str, ...]
    perfumer: str
    longevity: int
    sillage: int
    seasons: tuple[str, ...]
    occasions: tuple[str, ...]
    color: str
    price_50: int


PERFUMES: list[Perfume] = [
    Perfume("Figue Noire", "unisex", "nocturne-parfums", "Woody", "EDP", ("fig leaf", "bergamot"), ("fig milk", "iris"), ("cedar", "ambrette"), "Léa Marchetti", 4, 3, ("autumn", "winter"), ("evening", "office"), "4b2e24", 8900),
    Perfume("Sampaguita Absolue", "women", "nocturne-parfums", "Floral", "Parfum", ("green pear", "pink pepper"), ("sampaguita", "tuberose"), ("musk", "sandalwood"), "Isa Ventura", 5, 4, ("spring", "summer"), ("wedding", "evening"), "f2ebdd", 12800),
    Perfume("Calamansi Cologne", "unisex", "nocturne-parfums", "Citrus", "EDC", ("calamansi", "lime", "petitgrain"), ("neroli", "basil"), ("white musk", "vetiver"), "Isa Ventura", 2, 2, ("summer",), ("day", "beach"), "d9d36b", 4200),
    Perfume("Pili Gourmand", "niche", "nocturne-parfums", "Gourmand", "EDP", ("toasted pili", "cardamom"), ("tonka", "salted caramel"), ("vanilla", "benzoin"), "Daniel Okafor", 5, 4, ("autumn", "winter"), ("date night",), "b08457", 9600),
    Perfume("Ylang Mer", "women", "nocturne-parfums", "Floral", "EDP", ("sea salt", "mandarin"), ("ylang-ylang", "jasmine sambac"), ("driftwood", "musk"), "Léa Marchetti", 3, 3, ("summer",), ("day", "vacation"), "e8b4b8", 7800),
    Perfume("Oud Kintsugi", "niche", "nocturne-parfums", "Amber", "Parfum", ("saffron", "pink pepper"), ("rose", "oud"), ("amber", "labdanum", "patchouli"), "Daniel Okafor", 5, 5, ("winter",), ("evening", "special occasion"), "6b1e2e", 12500),
    Perfume("Vetiver Nuit", "men", "nocturne-parfums", "Woody", "EDP", ("grapefruit", "black pepper"), ("vetiver", "clary sage"), ("cedar", "smoky birch"), "Marc Delorme", 4, 3, ("autumn", "spring"), ("office", "evening"), "1f2a44", 7600),
    Perfume("Cuir Obscur", "men", "nocturne-parfums", "Leather", "EDP", ("bergamot", "elemi"), ("leather", "violet leaf"), ("birch tar", "tonka"), "Marc Delorme", 4, 4, ("autumn", "winter"), ("evening",), "1c1a1d", 8800),
    Perfume("Néroli Lumière", "women", "rue-solenne", "Citrus", "EDT", ("neroli", "bitter orange"), ("orange blossom", "petitgrain"), ("white musk",), "Claire Bastide", 3, 2, ("spring", "summer"), ("day", "office"), "ffd59a", 6400),
    Perfume("Iris Poudré", "women", "rue-solenne", "Floral", "EDP", ("aldehydes", "carrot seed"), ("orris butter", "violet"), ("suede", "musk"), "Claire Bastide", 4, 2, ("autumn", "spring"), ("office", "day"), "c9b6ff", 9200),
    Perfume("Santal Brume", "unisex", "rue-solenne", "Woody", "EDP", ("cardamom", "fig"), ("sandalwood", "papyrus"), ("cedar", "leather"), "Claire Bastide", 4, 3, ("autumn", "winter"), ("everyday",), "d8c3a5", 8400),
    Perfume("Ciel Salé", "unisex", "rue-solenne", "Fresh", "EDT", ("sea salt", "grapefruit"), ("sage", "ambrette"), ("driftwood", "ambroxan"), "Claire Bastide", 3, 3, ("summer", "spring"), ("day", "beach"), "9cc4d8", 6900),
    Perfume("Thé Matcha", "niche", "rue-solenne", "Aromatic", "EDP", ("matcha", "yuzu"), ("fig leaf", "jasmine tea"), ("hinoki", "musk"), "Hana Morita", 3, 2, ("spring",), ("office", "day"), "9caf88", 8600),
    Perfume("Bois de Mangue", "unisex", "nocturne-parfums", "Fresh", "EDT", ("green mango", "lime"), ("mango leaf", "coconut water"), ("vetiver", "musk"), "Isa Ventura", 3, 2, ("summer",), ("vacation", "day"), "d9d36b", 5800),
    Perfume("Tabac Doré", "men", "nocturne-parfums", "Amber", "Parfum", ("rum", "cinnamon"), ("tobacco leaf", "honey"), ("vanilla", "oakmoss"), "Marc Delorme", 5, 4, ("winter",), ("evening", "special occasion"), "c9a44c", 11200),
    Perfume("Rose Ilaya", "women", "nocturne-parfums", "Floral", "EDP", ("lychee", "pink pepper"), ("turkish rose", "peony"), ("patchouli", "musk"), "Léa Marchetti", 4, 4, ("spring",), ("date night", "wedding"), "e8b4b8", 8200),
    Perfume("Chypre Moderne", "women", "rue-solenne", "Chypre", "EDP", ("bergamot", "mandarin"), ("rose", "jasmine"), ("oakmoss", "patchouli"), "Claire Bastide", 4, 3, ("autumn",), ("office", "evening"), "6b6b3a", 9400),
    Perfume("Fougère Bleu", "men", "nocturne-parfums", "Fougère", "EDT", ("lavender", "bergamot"), ("geranium", "clary sage"), ("tonka", "oakmoss"), "Marc Delorme", 3, 3, ("spring", "autumn"), ("office", "everyday"), "2f4bff", 6200),
    Perfume("The Discovery Set", "gift-sets", "nocturne-parfums", "Woody", "EDP", ("bergamot", "calamansi"), ("sampaguita", "fig milk"), ("cedar", "vanilla"), "House blend", 3, 3, ("spring", "summer", "autumn", "winter"), ("gift",), "1f2a44", 4800),
    Perfume("Coffret Nuit", "gift-sets", "nocturne-parfums", "Amber", "Parfum", ("saffron", "rum"), ("rose", "tobacco leaf"), ("amber", "vanilla"), "House blend", 5, 4, ("winter",), ("gift", "evening"), "1c1a1d", 9800),
]  # fmt: skip

COLLECTIONS = [
    ("the-quiet-luxury-edit", "The Quiet Luxury Edit", "The Edit", "quiet-luxury",
     "No logos. Just cloth, cut, and patience.",
     "Pieces that whisper: double-faced wool, bias-cut silk, and leather that only gets better. "
     "Chosen for construction you can feel and colors that never shout.", "Camel", "coat", True),
    ("citrus-and-sun", "Citrus & Sun", "Season", "citrus-sun",
     "Bright notes and woven textures for long days.",
     "Calamansi colognes, abaca espadrilles, raffia hats and acetate frames: the wardrobe for "
     "a season spent outdoors.", "Citron", "sunglasses", False),
    ("after-hours", "After Hours", "Evening", "after-hours",
     "For candlelight, late dinners and the walk home.",
     "Minaudières, slingbacks and ambered scents with serious sillage. Everything here was "
     "chosen to look its best after dark.", "Bordeaux", "clutch", False),
]  # fmt: skip

REVIEW_LINES = {
    "clothing": [
        (
            "The drape is unreal",
            "Fabric has real weight and moves beautifully. Seams are clean inside, too.",
        ),
        (
            "Worth the wait",
            "Exactly as described. I'm 165 cm and the length hits right where the photos show.",
        ),
        (
            "Beautiful, size up",
            "Gorgeous cloth, but the shoulders are cut close. Consider one size up.",
        ),
        ("A forever piece", "You can tell it was finished by hand. The buttons alone are lovely."),
    ],
    "shoes": [
        (
            "Comfortable from day one",
            "The last is generous through the toe box. No break-in needed.",
        ),
        (
            "Runs a touch small",
            "Beautiful welt and sole, but I went half a size up and it's perfect.",
        ),
        (
            "Marikina craft at its best",
            "Stitching is immaculate. These will be resoled, not replaced.",
        ),
    ],
    "bags": [
        ("Holds everything", "Fits my phone, wallet, keys and sunglasses with room to spare."),
        (
            "Hardware is heavy, in a good way",
            "Clasp closes with a satisfying click. Leather edges are perfectly painted.",
        ),
        ("Structured but light", "Keeps its shape even when empty. The strap drop is just right."),
    ],
    "accessories": [
        (
            "Even better in person",
            "The finish catches the light beautifully. Arrived in a lovely box.",
        ),
        ("Everyday luxury", "I haven't taken it off since it arrived. Feels substantial."),
        ("Perfect gift", "Bought it for my sister and she cried. Packaging was impeccable."),
    ],
    "perfumes": [
        (
            "Compliment magnet",
            "Lasts all day on me and the drydown is gorgeous. Projection is moderate after an hour.",
        ),
        (
            "Smells like home",
            "The local botanicals make this feel so personal. Bought the 100 ml after the 30.",
        ),
        (
            "Elegant, not loud",
            "Close to the skin after a few hours but beautiful. Great for the office.",
        ),
        (
            "Signature-scent material",
            "Opens bright, settles into something warm and woody. I'm hooked.",
        ),
    ],
}
