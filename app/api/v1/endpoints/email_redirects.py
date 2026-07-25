"""
Email redirect endpoints.
These are clicked from email — redirect browser to splito:// deep link.
Flow: email button → this endpoint → 302 → splito://app/... → Flutter app opens
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings

router = APIRouter(tags=["Email Redirects"])


def _deep_link_page(deep_link: str, action: str) -> str:
    """
    Fallback HTML page if browser blocks the redirect.
    Shows a button + instructions to open the app manually.
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Splito — {action}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f4f4f5;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      padding: 40px 32px;
      max-width: 400px;
      width: 100%;
      text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }}
    .logo {{
      font-size: 48px;
      margin-bottom: 16px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 8px;
    }}
    p {{
      color: #6b7280;
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 28px;
    }}
    .btn {{
      display: inline-block;
      background: #6366f1;
      color: #fff;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      width: 100%;
    }}
    .note {{
      font-size: 13px;
      color: #9ca3af;
      margin-top: 20px;
    }}
  </style>
  <!-- Auto-redirect immediately -->
  <script>
    window.onload = function() {{
      window.location.href = "{deep_link}";
    }};
  </script>
</head>
<body>
  <div class="card">
    <div class="logo">💸</div>
    <h1>Opening Splito...</h1>
    <p>
      If the app doesn't open automatically,
      tap the button below.
    </p>
    <a href="{deep_link}" class="btn">Open Splito App</a>
    <p class="note">
      Make sure the Splito app is installed on your device.
    </p>
  </div>
</body>
</html>
"""


@router.get(
    "/auth/verify-email{token}",
    response_class=HTMLResponse,
    summary="Email verification redirect",
    description="Clicked from email — redirects to splito:// deep link to open Flutter app.",
    include_in_schema=False,  # hide from Swagger — not a public API
)
async def verify_email_redirect(token: str):
    deep_link = f"splito://app/verify-email?token={token}"
    return HTMLResponse(content=_deep_link_page(deep_link, "Verify Email"))


@router.get(
    "/auth/reset-password/{token}",
    response_class=HTMLResponse,
    summary="Password reset redirect",
    description="Clicked from email — redirects to splito:// deep link to open Flutter app.",
    include_in_schema=False,
)
async def reset_password_redirect(token: str):
    deep_link = f"splito://app/reset-password?token={token}"
    return HTMLResponse(content=_deep_link_page(deep_link, "Reset Password"))
