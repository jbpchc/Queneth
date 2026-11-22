# ruff: noqa: E501 — email HTML needs long inline-styled lines
"""Branded transactional email templates (HTML + plain text).

Inline styles only (email clients ignore <style>), table layout, 600px column.
Colors are the light-mode tokens. Later phases add order, shipping, seller and
drop templates with the same `layout()`.
"""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class RenderedEmail:
    template: str
    subject: str
    html: str
    text: str
    #: Shown in the in-app inbox; `action_url` only when safe to keep there.
    inbox_title: str
    inbox_body: str
    inbox_action_url: str | None = None


INK, MUTED, BG, ACCENT, BORDER = "#141214", "#6B6470", "#FAF7F2", "#C8136E", "#E6DED2"
FOOTER = "QueWallet credits are simulated for academic purposes and have no cash value."


def layout(*, preheader: str, heading: str, body_html: str, cta_label: str, cta_url: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:{BG};font-family:Manrope,Helvetica,Arial,sans-serif;color:{INK}">
<span style="display:none;max-height:0;overflow:hidden">{escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:32px 16px">
<tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid {BORDER};border-radius:20px">
<tr><td style="padding:32px 40px 0;font-family:Georgia,serif;font-size:28px;font-weight:600;letter-spacing:-0.5px">Queneth<span style="color:{ACCENT}">.</span></td></tr>
<tr><td style="padding:24px 40px 8px;font-family:Georgia,serif;font-size:30px;line-height:1.15">{escape(heading)}</td></tr>
<tr><td style="padding:8px 40px 24px;font-size:16px;line-height:1.6;color:{INK}">{body_html}</td></tr>
<tr><td style="padding:0 40px 32px"><a href="{escape(cta_url, quote=True)}" style="display:inline-block;background:{ACCENT};color:#fff;text-decoration:none;font-weight:700;padding:14px 28px;border-radius:999px">{escape(cta_label)}</a></td></tr>
<tr><td style="padding:0 40px 32px;font-size:13px;line-height:1.5;color:{MUTED}">If the button doesn't work, paste this link into your browser:<br><a href="{escape(cta_url, quote=True)}" style="color:#2F4BFF;word-break:break-all">{escape(cta_url)}</a></td></tr>
</table>
<p style="max-width:600px;font-size:12px;line-height:1.5;color:{MUTED};margin:16px auto 0">Curated for the connoisseur. {FOOTER}</p>
</td></tr></table></body></html>"""


def verify_email(*, name: str, url: str) -> RenderedEmail:
    raw = name.split()[0] if name else "there"
    return RenderedEmail(
        template="verify_email",
        subject="Confirm your email for Queneth",
        html=layout(
            preheader="One tap to confirm your email.",
            heading=f"Welcome, {raw}.",
            body_html="Confirm your email so we can send order updates, drop alerts and receipts. "
            "This link works for 48 hours.",
            cta_label="Confirm email",
            cta_url=url,
        ),
        text=f"Welcome to Queneth, {raw}.\n\nConfirm your email (link valid for 48 hours):\n{url}\n\n{FOOTER}",
        inbox_title="Confirm your email",
        inbox_body="We sent a confirmation link to your inbox. You can also confirm from here.",
        inbox_action_url=url,
    )


def password_reset(*, name: str, url: str) -> RenderedEmail:
    raw = name.split()[0] if name else "there"
    first = escape(raw)
    return RenderedEmail(
        template="password_reset",
        subject="Reset your Queneth password",
        html=layout(
            preheader="Reset link inside — valid for 1 hour.",
            heading="Reset your password",
            body_html=f"Hi {first}, someone (hopefully you) asked to reset your password. "
            "The link works once and expires in 1 hour. If it wasn't you, ignore this email; "
            "your password stays the same.",
            cta_label="Choose a new password",
            cta_url=url,
        ),
        text=f"Hi {raw},\n\nReset your Queneth password (valid 1 hour, one use):\n{url}\n\n"
        f"If you didn't ask for this, ignore this email.\n\n{FOOTER}",
        inbox_title="Password reset requested",
        # No link in the inbox: the reset link belongs in the mailbox only.
        inbox_body="A password reset link was emailed to you. If that wasn't you, you can ignore it.",
    )


def password_changed(*, name: str, url: str) -> RenderedEmail:
    raw = name.split()[0] if name else "there"
    first = escape(raw)
    return RenderedEmail(
        template="password_changed",
        subject="Your Queneth password was changed",
        html=layout(
            preheader="Your password was just changed.",
            heading="Password changed",
            body_html=f"Hi {first}, your password was changed and every other device was signed out. "
            "If this wasn't you, reset it again right away.",
            cta_label="Sign in",
            cta_url=url,
        ),
        text=f"Hi {raw}, your Queneth password was changed and other devices were signed out.\n"
        f"If this wasn't you, reset it again: {url}\n\n{FOOTER}",
        inbox_title="Password changed",
        inbox_body="Your password was changed and other devices were signed out.",
    )


def order_confirmation(
    *,
    name: str,
    number: str,
    total_qc: int,
    points: int,
    boutiques: list[tuple[str, list[tuple[str, int, int]]]],
    url: str,
    inbox_path: str,
) -> RenderedEmail:
    """`boutiques` = [(boutique name, [(item title, qty, line total QC), …]), …]."""
    raw = name.split()[0] if name else "there"
    rows_html = ""
    rows_text = ""
    for boutique, items in boutiques:
        rows_html += (
            f'<tr><td colspan="2" style="padding:16px 0 4px;font-size:12px;letter-spacing:1px;'
            f'text-transform:uppercase;color:{MUTED}">{escape(boutique)}</td></tr>'
        )
        rows_text += f"\n{boutique}\n"
        for title, qty, line in items:
            rows_html += (
                f'<tr><td style="padding:4px 0;border-bottom:1px solid {BORDER}">{escape(title)} × {qty}</td>'
                f'<td align="right" style="padding:4px 0;border-bottom:1px solid {BORDER};white-space:nowrap">{line:,} QC</td></tr>'
            )
            rows_text += f"  {title} x {qty}  {line:,} QC\n"
    body = (
        f"Thank you, {escape(raw)}. Your order <strong>{escape(number)}</strong> is paid and held safely "
        "in escrow until each boutique delivers. Every boutique ships its pieces separately."
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;font-size:15px">{rows_html}'
        f'<tr><td style="padding:12px 0 0;font-weight:700">Total paid</td><td align="right" style="padding:12px 0 0;font-weight:700">{total_qc:,} QC</td></tr></table>'
        f'<p style="margin:16px 0 0;color:{MUTED}">+{points:,} Que Points arrive when your order is delivered.</p>'
    )
    return RenderedEmail(
        template="order_confirmation",
        subject=f"Order {number} confirmed",
        html=layout(
            preheader=f"Paid {total_qc:,} QC with QueWallet. We'll tell you when it ships.",
            heading="Your order is confirmed.",
            body_html=body,
            cta_label="View your order",
            cta_url=url,
        ),
        text=(
            f"Thank you, {raw}. Order {number} is confirmed and paid ({total_qc:,} QC).\n{rows_text}\n"
            f"+{points:,} Que Points when delivered.\n\nView your order: {url}\n\n{FOOTER}"
        ),
        inbox_title=f"Order {number} confirmed",
        inbox_body=f"Paid {total_qc:,} QC. We'll let you know when each boutique ships.",
        inbox_action_url=inbox_path,
    )


def order_update(
    *,
    template: str,
    name: str,
    subject: str,
    heading: str,
    body: str,
    url: str,
    inbox_path: str,
    cta_label: str = "View your order",
) -> RenderedEmail:
    """Status emails (shipped, delivered, cancelled, refunded …). `body` is plain text."""
    raw = name.split()[0] if name else "there"
    return RenderedEmail(
        template=template,
        subject=subject,
        html=layout(
            preheader=body,
            heading=heading,
            body_html=f"Hi {escape(raw)}, {escape(body)}",
            cta_label=cta_label,
            cta_url=url,
        ),
        text=f"Hi {raw}, {body}\n\n{cta_label}: {url}\n\n{FOOTER}",
        inbox_title=subject,
        inbox_body=body,
        inbox_action_url=inbox_path,
    )
