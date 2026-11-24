"""The opt-in brand sellers seed: every piece belongs to its seller, and
re-running adds nothing."""

from sqlalchemy import func, select

from app.models import User
from app.models.catalog import Product, SellerProfile
from app.seed.base import seed_base
from app.seed.brand_sellers import ITEMS, seed_brand_sellers


async def test_brand_sellers_seed(client, db):
    await seed_base(db)
    first = await seed_brand_sellers(db)
    assert first == {"sellers": 3, "products": sum(len(v) for v in ITEMS.values()), "buyers": 2}
    assert await seed_brand_sellers(db) == {"sellers": 0, "products": 0, "buyers": 0}
    # Stores are seller-only accounts; the demo shoppers are buyer-only.
    roles = dict((await db.execute(select(User.email, User.roles))).all())
    assert roles["nike@queneth.test"] == ["SELLER"]
    assert roles["buyer@queneth.test"] == roles["collector@queneth.test"] == ["BUYER"]

    rows = (
        await db.execute(
            select(SellerProfile.slug, func.count(Product.id))
            .join(Product, Product.seller_id == SellerProfile.id)
            .group_by(SellerProfile.slug)
        )
    ).all()
    assert dict(rows) == {k: len(v) for k, v in ITEMS.items()}

    home = (await client.get("/api/v1/catalog/home")).json()
    assert {b["slug"] for b in home["featured_boutiques"]} == {"nike", "penshoppe", "bench"}
    nike = (await client.get("/api/v1/catalog/boutiques/nike")).json()
    assert nike["name"] == "Nike"
    deals = (await client.get("/api/v1/catalog/deals")).json()
    assert len(deals["on_sale"]) == 3  # the pieces with a genuine markdown
