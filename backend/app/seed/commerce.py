"""Commerce seed: seller vouchers and demo shipping addresses. Idempotent.

Addresses are resolved through the same PSGC snapshot the API uses, so the
place names match what the address picker shows.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.models.catalog import SellerProfile
from app.models.commerce import Address, Voucher
from app.services.geo_service import GeoService

# (code, boutique slug, type, value, min spend QC, max uses, description)
DEMO_VOUCHERS = [
    ("LUMEN10", "atelier-lumen", "percent", 10, 3_000, 200, "10% off Atelier Lumen from 3,000 QC"),
    ("OBRA500", "obra-leather", "fixed", 500, 5_000, 200, "500 QC off Obra Leather from 5,000 QC"),
    (
        "NOCTURNE15",
        "nocturne-parfums",
        "percent",
        15,
        4_000,
        150,
        "15% off Nocturne Parfums from 4,000 QC",
    ),
    (
        "ILAYA-SUN",
        "casa-ilaya",
        "fixed",
        1_000,
        8_000,
        100,
        "1,000 QC off Casa Ilaya from 8,000 QC",
    ),
]

# (email, label, recipient, phone, line1, barangay code, zip, default)
DEMO_ADDRESSES = [
    (
        "buyer@queneth.test",
        "Home",
        "Bea Santos",
        "+639171234567",
        "18 Amorsolo St., Unit 7C",
        "137602002",
        "1209",
        True,
    ),
    (
        "buyer@queneth.test",
        "Office",
        "Bea Santos",
        "+639171234567",
        "Peñafrancia Ave., 3/F Plaza Rizal Bldg.",
        "051724003",
        "4400",
        False,
    ),
    (
        "seller@queneth.test",
        "Studio",
        "Atelier Lumen Studio",
        "+639189876543",
        "1440 M.H. del Pilar St., Ermita",
        "137404001",
        "1100",
        True,
    ),
]


async def seed_commerce(session: AsyncSession) -> dict[str, int]:
    sellers = {s.slug: s for s in (await session.scalars(select(SellerProfile))).all()}
    have = set((await session.scalars(select(Voucher.code))).all())
    vouchers = 0
    for code, slug, kind, value, min_spend, uses, desc in DEMO_VOUCHERS:
        if code in have or slug not in sellers:
            continue
        session.add(
            Voucher(
                seller_id=sellers[slug].id,
                code=code,
                type=kind,
                value=value,
                min_spend_qc=min_spend,
                max_uses=uses,
                used_count=0,
                is_active=True,
                description=desc,
            )
        )
        vouchers += 1

    geo = GeoService(session, get_settings())
    addresses = 0
    for email, label, recipient, phone, line1, brgy, zip_code, default in DEMO_ADDRESSES:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            continue
        exists = await session.scalar(
            select(Address.id).where(Address.user_id == user.id, Address.label == label)
        )
        if exists:
            continue
        names = geo.resolve_barangay(brgy)
        session.add(
            Address(
                user_id=user.id,
                label=label,
                recipient=recipient,
                phone=phone,
                line1=line1,
                barangay_code=brgy,
                barangay=names["barangay"] or "",
                city=names["city"] or "",
                province=names["province"],
                region=names["region"] or "",
                zip=zip_code,
                is_default=default,
            )
        )
        addresses += 1
    await session.commit()
    return {"vouchers": vouchers, "addresses": addresses}
