import logging
import secrets
from email.message import EmailMessage

import aiosmtplib

from app.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def generate_verification_code() -> str:
        """6자리 보안 난수 인증 코드를 생성합니다."""
        return f"{secrets.randbelow(900000) + 100000}"

    @classmethod
    async def send_verification_email(cls, to_email: str, code: str) -> None:
        """
        회원가입 6자리 인증 코드를 Gmail SMTP를 통해 발송합니다.
        SMTP 설정이 비어있거나 로컬 테스트 모드일 경우 로그만 남기고 정상 종료합니다.
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                "[EmailService] SMTP credentials not set. Simulated code for %s: %s",
                to_email,
                code,
            )
            return

        msg = EmailMessage()
        msg["Subject"] = f"[{settings.SMTP_FROM_NAME}] 회원가입 인증 번호 [{code}]"
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = to_email

        # 텍스트 본문 (HTML 미지원 클라이언트용)
        text_content = (
            f"안녕하세요, Don't Paw-get Your Book(도서관 사서단)입니다.\n\n"
            f"회원가입을 완료하기 위해 아래 6자리 인증 번호를 입력해 주세요:\n"
            f"인증 번호: {code}\n\n"
            f"해당 번호는 {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES}분 동안 유효합니다.\n"
            f"본인이 요청하지 않은 경우 이 메일을 무시해 주세요.\n"
        )
        msg.set_content(text_content)

        # HTML 본문 (반응형 카드 템플릿)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>회원가입 인증 번호</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f7f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f7f9fa; padding: 40px 10px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 500px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 20px 32px; text-align: center; border-bottom: 1px solid #f0f2f5;">
              <h2 style="margin: 0 0 8px 0; color: #1e293b; font-size: 20px; font-weight: 700;">🐾 Don't Paw-get Your Book</h2>
              <p style="margin: 0; color: #64748b; font-size: 14px;">도서관 사서단 회원가입 이메일 인증</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 16px 0; color: #334155; font-size: 15px; line-height: 1.6;">
                안녕하세요! <strong>Don't Paw-get Your Book</strong>에 오신 것을 환영합니다.<br>
                회원가입 화면에서 아래 <strong>6자리 인증 번호</strong>를 입력해 주세요.
              </p>
              
              <!-- Code Box -->
              <div style="margin: 28px 0; padding: 20px; background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; text-align: center;">
                <span style="font-family: monospace, Courier, sans-serif; font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #0284c7;">
                  {code}
                </span>
              </div>

              <p style="margin: 0; color: #64748b; font-size: 13px; line-height: 1.5; text-align: center;">
                ⏳ 해당 인증 코드는 <strong>{settings.EMAIL_VERIFICATION_EXPIRE_MINUTES}분간</strong> 유효합니다.<br>
                본인이 요청하지 않았다면 메일을 안전하게 삭제해 주세요.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #f8fafc; text-align: center; border-top: 1px solid #f0f2f5;">
              <p style="margin: 0; color: #94a3b8; font-size: 12px;">
                © 2026 Don't Paw-get Your Book. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
        msg.add_alternative(html_content, subtype="html")

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True,
                timeout=15.0,
            )
            logger.info("[EmailService] Verification email successfully sent to %s", to_email)
        except Exception as e:
            logger.error("[EmailService] Failed to send email to %s: %s", to_email, e)
            raise AppException(
                502,
                "EMAIL_SEND_FAILED",
                "인증 메일 전송 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            ) from e
