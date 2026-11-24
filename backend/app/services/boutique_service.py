"""Seller applications, approval decisions, and the boutique's storefront settings."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import Permission, Role, assert_can
from app.core.security import utcnow
from app.core.text import slugify
from app.models.catalog import Product, SellerProfile
from app.models.integration import EmailLog
from app.models.user import User
from app.schemas.studio import (
    BoutiqueSettingsIn,
    BoutiqueSettingsOut,
    LookbookImage,
    SellerApplicationIn,
    SellerApplicationOut,
)
from app.services import audit_service, email_service, email_templates
from app.services.media_service import MediaService


async def _unique_slug(session: AsyncSession, name: str, exclude: uuid.UUID | None = None) -> str:
    base = slugify(name)[:70] or "boutique"
    slug, n = base, 2
    while True:
        stmt = select(SellerProfile.id).where(SellerProfile.slug == slug)
        if exclude:
            stmt = stmt.where(SellerProfile.id != exclude)
        if await session.scalar(stmt) is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


async def _name_taken(session: AsyncSession, name: str, exclude: uuid.UUID | None) -> bool:
    stmt = select(SellerProfile.id).where(func.lower(SellerProfile.boutique_name) == name.lower())
    if exclude:
        stmt = stmt.where(SellerProfile.id != exclude)
    return await session.scalar(stmt) is not None


async def _asset_url(media: MediaService, user: User, asset_id: uuid.UUID | None) -> str | None:
    if asset_id is None:
        return None
    asset = await media.get_ready_asset(user, asset_id, "boutique")
    return media.to_out(asset).url


def application_out(p: SellerProfile, abs_url) -> SellerApplicationOut:  # type: ignore[no-untyped-def]
    return SellerApplicationOut(
        id=p.id,
        boutique_name=p.boutique_name,
        slug=p.slug,
        tagline=p.tagline,
        bio=p.bio,
        return_policy=p.return_policy,
        contact_email=p.contact_email,
        city=p.city,
        logo_url=abs_url(p.logo_url),
        banner_url=abs_url(p.banner_url),
        status=p.status,  # type: ignore[arg-type]
        rejection_reason=p.rejection_reason,
        created_at=p.created_at,
    )


# ─── Applying ──────────────────────────────────────────────────────────────


async def mine(session: AsyncSession, user: User) -> SellerProfile | None:
    return await session.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))


async def apply(
    session: AsyncSession, settings: Settings, user: User, body: SellerApplicationIn
) -> SellerProfile:
    """Submit (or, after a rejection, resubmit) a boutique application."""
    existing = await mine(session, user)
    if existing is None:
        assert_can(user, Permission.SELLER_APPLY)
    elif existing.status in ("approved", "suspended"):
        raise Conflict("You already have a boutique.", code="already_seller")
    # A pending application can be edited; a rejected one is resubmitted as pending.
    if await _name_taken(session, body.boutique_name, existing.id if existing else None):
        raise Conflict("Another boutique already uses that name.", code="boutique_name_taken")

    media = MediaService(session, settings)
    profile = existing or SellerProfile(user_id=user.id)
    profile.boutique_name = body.boutique_name
    profile.slug = await _unique_slug(session, body.boutique_name, profile.id if existing else None)
    profile.tagline = body.tagline or None
    profile.bio = body.bio.strip()
    profile.return_policy = body.return_policy.strip()
    profile.contact_email = str(body.contact_email)
    profile.city = body.city
    if (logo := await _asset_url(media, user, body.logo_asset_id)) is not None:
        profile.logo_url = logo
    if (banner := await _asset_url(media, user, body.banner_asset_id)) is not None:
        profile.banner_url = banner
    profile.status = "pending"
    profile.rejection_reason = None
    if existing is None:
        session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


# ─── Deciding (admin; the Control Room screen arrives in Phase 9) ──────────


async def decide(
    session: AsyncSession,
    settings: Settings,
    admin: User,
    seller_id: uuid.UUID,
    approve: bool,
    reason: str | None,
    ip: str | None,
) -> tuple[SellerProfile, EmailLog]:
    assert_can(admin, Permission.SELLER_APPROVE)
    profile = await session.get(SellerProfile, seller_id)
    if profile is None:
        raise NotFound("We couldn't find that application.", code="application_not_found")
    if profile.status != "pending":
        raise Conflict("Only pending applications can be decided.", code="not_pending")
    if not approve and not (reason or "").strip():
        raise ValidationFailed("Tell the applicant why.", code="reason_required")
    owner = await session.get(User, profile.user_id)
    assert owner is not None
    before = {"status": profile.status}
    if approve:
        profile.status = "approved"
        profile.approved_by = admin.id
        profile.approved_at = utcnow()
        owner.roles = [Role.SELLER.value]  # one role per account: sellers don't shop
        email = email_templates.order_update(
            template="seller_approved",
            name=owner.name,
            subject=f"{profile.boutique_name} is approved",
            heading="Welcome to Seller Studio.",
            body=f"{profile.boutique_name} is approved. Add your first piece and start selling.",
            url=f"{settings.frontend_url}/seller",
            inbox_path="/seller",
            cta_label="Open Seller Studio",
        )
    else:
        profile.status = "rejected"
        profile.rejection_reason = (reason or "").strip()
        email = email_templates.order_update(
            template="seller_rejected",
            name=owner.name,
            subject=f"About your {profile.boutique_name} application",
            heading="Not quite yet.",
            body=f"We couldn't approve {profile.boutique_name}: {profile.rejection_reason} "
            "You can update your application and send it again.",
            url=f"{settings.frontend_url}/account/sell",
            inbox_path="/account/sell",
            cta_label="Update your application",
        )
    entry = email_service.queue(session, user=owner, to_email=owner.email, email=email)
    audit_service.record(
        session,
        actor_id=admin.id,
        action="seller.approve" if approve else "seller.reject",
        target_type="seller_profile",
        target_id=profile.id,
        before=before,
        after={"status": profile.status, "reason": profile.rejection_reason},
        ip=ip,
    )
    await session.commit()
    return profile, entry


async def pending(session: AsyncSession, admin: User) -> list[SellerProfile]:
    assert_can(admin, Permission.SELLER_APPROVE)
    return list(
        (
            await session.scalars(
                select(SellerProfile)
                .where(SellerProfile.status == "pending")
                .order_by(SellerProfile.created_at)
            )
        ).all()
    )


# ─── Storefront settings ───────────────────────────────────────────────────


def own_boutique(user: User) -> uuid.UUID:
    if user.seller_id is None:
        raise PermissionDenied("Your boutique isn't approved yet.", code="seller_not_approved")
    return user.seller_id


def settings_out(p: SellerProfile, abs_url) -> BoutiqueSettingsOut:  # type: ignore[no-untyped-def]
    return BoutiqueSettingsOut(
        **application_out(p, abs_url).model_dump(),
        featured_product_ids=[uuid.UUID(i) for i in (p.featured_product_ids or [])],
        lookbook=[
            LookbookImage(url=abs_url(x["url"]) or x["url"], caption=x.get("caption"))
            for x in (p.lookbook or [])
        ],
    )


async def update_settings(
    session: AsyncSession, settings: Settings, user: User, body: BoutiqueSettingsIn
) -> SellerProfile:
    seller_id = own_boutique(user)
    profile = await session.get(SellerProfile, seller_id)
    assert profile is not None
    media = MediaService(session, settings)
    profile.tagline = body.tagline or None
    profile.bio = body.bio.strip()
    profile.return_policy = body.return_policy.strip()
    profile.contact_email = str(body.contact_email)
    profile.city = body.city
    if (logo := await _asset_url(media, user, body.logo_asset_id)) is not None:
        profile.logo_url = logo
    if (banner := await _asset_url(media, user, body.banner_asset_id)) is not None:
        profile.banner_url = banner

    featured = list(dict.fromkeys(body.featured_product_ids))
    if featured:
        own_active = set(
            (
                await session.scalars(
                    select(Product.id).where(
                        Product.id.in_(featured),
                        Product.seller_id == seller_id,
                        Product.status == "active",
                        Product.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        if len(own_active) != len(featured):
            raise ValidationFailed(
                "Featured pieces must be your own published products.", code="invalid_featured"
            )
    profile.featured_product_ids = [str(i) for i in featured]

    current = {x["url"]: x for x in (profile.lookbook or [])}
    look: list[dict[str, str]] = []
    for item in body.lookbook:
        if item.asset_id:
            url = await _asset_url(media, user, item.asset_id)
        else:
            # Keep an image already in the lookbook. The API returns absolute
            # URLs, so match them back to the stored (possibly relative) ones.
            url = next(
                (k for k in current if item.url and (item.url == k or item.url.endswith(k))), None
            )
            if url is None:
                raise ValidationFailed(
                    "Lookbook images must be uploaded first.", code="invalid_lookbook"
                )
        entry = {"url": url or ""}
        if item.caption:
            entry["caption"] = " ".join(item.caption.split())
        look.append(entry)
    profile.lookbook = look
    await session.commit()
    await session.refresh(profile)
    return profile


async def dismiss_first_sale(session: AsyncSession, user: User) -> None:
    profile = await session.get(SellerProfile, own_boutique(user))
    if profile is not None and profile.first_sale_seen_at is None:
        profile.first_sale_seen_at = utcnow()
        await session.commit()
