"""
Email service using Resend API.
All sending is fire-and-forget safe — errors are logged, never raised.
"""
import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


# ─── HTML Templates ───────────────────────────────────────────────────────────

def _base_template(content: str) -> str:
    """Wraps content in a clean, mobile-friendly email shell."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Splito</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:#6366f1;padding:32px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;
                         letter-spacing:-0.5px;">💸 Splito</h1>
              <p style="margin:6px 0 0;color:#c7d2fe;font-size:14px;">
                Expense splitting made simple
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f9fafb;padding:20px 40px;text-align:center;
                       border-top:1px solid #e5e7eb;">
              <p style="margin:0;color:#9ca3af;font-size:12px;">
                © 2026 Splito · This email was sent to you because you have an account with Splito.
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


def _verification_email_html(name: str, verify_url: str) -> str:
    content = f"""
      <h2 style="margin:0 0 8px;color:#111827;font-size:22px;font-weight:600;">
        Verify your email address
      </h2>
      <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
        Hi {name}, welcome to Splito! Please verify your email address to
        activate your account and start splitting expenses with your friends.
      </p>

      <div style="text-align:center;margin:32px 0;">
        <a href="{verify_url}"
           style="display:inline-block;background:#6366f1;color:#ffffff;
                  text-decoration:none;padding:14px 36px;border-radius:8px;
                  font-size:15px;font-weight:600;letter-spacing:0.2px;">
          Verify Email Address
        </a>
      </div>

      <p style="margin:24px 0 0;color:#9ca3af;font-size:13px;text-align:center;">
        This link expires in <strong>24 hours</strong>.<br/>
        If you didn't create a Splito account, you can safely ignore this email.
      </p>

      <div style="margin:28px 0 0;padding:16px;background:#f3f4f6;
                  border-radius:8px;word-break:break-all;">
        <p style="margin:0;color:#6b7280;font-size:12px;">
          Or copy this link into your browser:<br/>
          <span style="color:#6366f1;">{verify_url}</span>
        </p>
      </div>
    """
    return _base_template(content)


def _reset_password_email_html(name: str, reset_url: str) -> str:
    content = f"""
      <h2 style="margin:0 0 8px;color:#111827;font-size:22px;font-weight:600;">
        Reset your password
      </h2>
      <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
        Hi {name}, we received a request to reset the password for your Splito account.
        Click the button below to choose a new password.
      </p>

      <div style="text-align:center;margin:32px 0;">
        <a href="{reset_url}"
           style="display:inline-block;background:#ef4444;color:#ffffff;
                  text-decoration:none;padding:14px 36px;border-radius:8px;
                  font-size:15px;font-weight:600;letter-spacing:0.2px;">
          Reset Password
        </a>
      </div>

      <div style="margin:24px 0;padding:16px;background:#fef3c7;
                  border-radius:8px;border-left:4px solid #f59e0b;">
        <p style="margin:0;color:#92400e;font-size:13px;">
          ⚠️ This link expires in <strong>15 minutes</strong> for your security.<br/>
          If you didn't request a password reset, please ignore this email —
          your password will not be changed.
        </p>
      </div>

      <div style="margin:16px 0 0;padding:16px;background:#f3f4f6;
                  border-radius:8px;word-break:break-all;">
        <p style="margin:0;color:#6b7280;font-size:12px;">
          Or copy this link into your browser:<br/>
          <span style="color:#ef4444;">{reset_url}</span>
        </p>
      </div>
    """
    return _base_template(content)


# ─── Send functions ───────────────────────────────────────────────────────────

async def send_verification_email(
    to_email: str,
    name: str,
    token: str,
) -> None:
    """
    Sends email verification link.
    Never raises — logs error and returns silently on failure.
    """
    verify_url = (
        f"{settings.frontend_url}/verify-email/{token}"
    )
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Verify your Splito email address",
            "html": _verification_email_html(name, verify_url),
        })
        logger.info("Verification email sent to %s", to_email)
    except Exception as exc:
        logger.error(
            "Failed to send verification email to %s: %s", to_email, exc,
            exc_info=True,
        )


async def send_password_reset_email(
    to_email: str,
    name: str,
    token: str,
) -> None:
    """
    Sends password reset link.
    Never raises — logs error and returns silently on failure.
    """
    reset_url = (
        f"{settings.frontend_url}/reset-password/{token}"
    )
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Reset your Splito password",
            "html": _reset_password_email_html(name, reset_url),
        })
        logger.info("Password reset email sent to %s", to_email)
    except Exception as exc:
        logger.error(
            "Failed to send password reset email to %s: %s", to_email, exc,
            exc_info=True,
        )
