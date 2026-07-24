"""Branded email templates (Slice 1 Phase A).

Email is not the web. The constraints below are why this looks nothing like the
app's markup:

* **Tables, not flex/grid.** Outlook renders through Word's HTML engine, which
  has no modern layout support at all.
* **Inline styles.** Gmail strips <style> blocks in several contexts, notably
  the mobile apps and forwarded mail.
* **Poppins will not load.** Almost no client honours @font-face or a Google
  Fonts link, so the brand face is declared first and a web-safe stack carries
  the actual rendering.
* **The wordmark is the real PNG**, served from the production host and shown
  on the orange band (white artwork). `alt="bluntly"` covers the ~half of
  inboxes that block remote images.
* **A gradient needs a solid fallback.** `background-color` is declared before
  `background-image` so clients that drop gradients still get brand orange
  rather than white.

Every message ships both an HTML and a plain-text part: a text alternative is a
real deliverability signal, and some recipients genuinely read text only.
"""

from __future__ import annotations

# Brand values, matching app/tokens/colors.css.
_ORANGE = "#ef5821"
_ORANGE_DEEP = "#963719"
_INK = "#202020"
_SURFACE = "#f2f2f2"
_WHITE = "#ffffff"
_MUTED = "rgba(32,32,32,0.62)"

# The wordmark PNG, served from the production site. White artwork, shown on the
# orange band. Override with EMAIL_LOGO_URL if the canonical domain changes.
_LOGO_URL = "https://www.bluntly.ph/bluntly-logo.png"

# Kept as its own constant so the style attribute stays inside the line limit.
_BRAND_GRADIENT = (
    f"linear-gradient(135deg,#ffc596 0%,{_ORANGE} 45%,{_ORANGE_DEEP} 100%)"
)

_FONT = (
    "'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)

OTP_SUBJECT = "{code} is your bluntly verification code"


def otp_subject(code: str) -> str:
    """Leading the subject with the code lets people verify from the preview."""
    return OTP_SUBJECT.format(code=code)


def otp_text(code: str, ttl_minutes: int) -> str:
    return (
        f"Your bluntly verification code is {code}\n\n"
        f"Enter it in the app to finish signing in. "
        f"It expires in {ttl_minutes} minutes and can only be used once.\n\n"
        "If you didn't request this, you can ignore this email — "
        "nobody can access your account without the code.\n\n"
        "---\n"
        "bluntly.ph — Honest reviews. Real Payouts.\n"
        "No sponsorships. No bias. Ever.\n"
    )


def otp_html(code: str, ttl_minutes: int) -> str:
    spaced_code = " ".join(code)
    return f"""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light" />
<meta name="supported-color-schemes" content="light" />
<title>Your bluntly verification code</title>
</head>
<body style="margin:0; padding:0; background-color:{_SURFACE};">

<!-- Preheader: the preview line in the inbox list. Hidden in the body itself. -->
<div style="display:none; font-size:1px; color:{_SURFACE}; line-height:1px;
            max-height:0; max-width:0; opacity:0; overflow:hidden;">
  Your code is {code}. It expires in {ttl_minutes} minutes.
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:{_SURFACE};">
  <tr>
    <td align="center" style="padding:32px 16px;">

      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
             style="width:600px; max-width:100%; border-collapse:collapse;">

        <!-- Brand band. Solid colour first so gradient-blind clients still get orange. -->
        <tr>
          <td align="center"
              style="background-color:{_ORANGE};
                     background-image:{_BRAND_GRADIENT};
                     border-radius:20px 20px 0 0; padding:34px 32px;">
            <!-- The real wordmark (white PNG) on the orange band. `alt` carries
                 the brand for the ~half of inboxes that block remote images. -->
            <img src="{_LOGO_URL}" alt="bluntly" width="132" height="41"
                 style="display:block; width:132px; height:41px; border:0;
                        margin:0 auto; outline:none; text-decoration:none;" />
          </td>
        </tr>

        <!-- Code card -->
        <tr>
          <td style="background-color:{_WHITE}; padding:40px 32px 32px;">
            <p style="margin:0 0 8px; font-family:{_FONT}; font-size:20px;
                      font-weight:600; color:{_INK};">Verify it&rsquo;s really you</p>
            <p style="margin:0 0 28px; font-family:{_FONT}; font-size:14px;
                      line-height:22px; color:{_MUTED};">
              Enter this code in the app to finish signing in.
            </p>

            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td align="center"
                    style="background-color:{_SURFACE}; border-radius:12px; padding:24px 16px;">
                  <span style="font-family:{_FONT}; font-size:34px; font-weight:700;
                               letter-spacing:10px; color:{_INK};
                               mso-line-height-rule:exactly; line-height:40px;">{spaced_code}</span>
                </td>
              </tr>
            </table>

            <p style="margin:24px 0 0; font-family:{_FONT}; font-size:13px;
                      line-height:20px; color:{_MUTED};">
              This code expires in <strong style="color:{_INK};">{ttl_minutes} minutes</strong>
              and can only be used once.
            </p>
            <p style="margin:12px 0 0; font-family:{_FONT}; font-size:13px;
                      line-height:20px; color:{_MUTED};">
              Didn&rsquo;t request it? You can ignore this email — nobody can get
              into your account without the code.
            </p>
          </td>
        </tr>

        <!-- Why we exist. Short, and in the product's own voice. -->
        <tr>
          <td style="background-color:{_WHITE}; padding:0 32px 32px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr><td style="border-top:1px solid rgba(32,32,32,0.10); padding-top:24px;">
                <p style="margin:0 0 6px; font-family:{_FONT}; font-size:15px;
                          font-weight:600; color:{_INK};">
                  Honest reviews. Real Payouts.
                </p>
                <p style="margin:0; font-family:{_FONT}; font-size:13px;
                          line-height:20px; color:{_MUTED};">
                  Filipinos making smarter purchases — and reviewers earning a
                  commission when their honest write-up drives a sale.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td align="center"
              style="background-color:{_INK}; border-radius:0 0 20px 20px; padding:24px 32px;">
            <p style="margin:0 0 6px; font-family:{_FONT}; font-size:13px;
                      font-weight:600; color:{_SURFACE};">bluntly.ph</p>
            <p style="margin:0; font-family:{_FONT}; font-size:11px;
                      line-height:18px; color:rgba(242,242,242,0.62);">
              No sponsorships. No bias. Ever.
            </p>
          </td>
        </tr>

        <tr>
          <td align="center" style="padding:20px 16px 0;">
            <p style="margin:0; font-family:{_FONT}; font-size:11px;
                      line-height:18px; color:{_MUTED};">
              You received this because someone asked for a sign-in code for this
              address. This is a one-off security message, not a newsletter.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""
