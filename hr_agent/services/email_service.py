import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from hr_agent.config import get_settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.settings = get_settings()

    def send_reset_password_email(self, email_to: str, reset_link: str) -> bool:
        if not self.settings.smtp_host or not self.settings.smtp_user:
            logger.warning("SMTP not configured. Cannot send email.")
            return False

        subject = "Password Reset Request - HR Platform"
        
        # HTML body
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hello,</p>
                <p>You requested a password reset for your HR Platform account.</p>
                <p>Please click the button below to reset your password:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p style="font-size: 0.9em; color: #666;">
                    If you did not request this, please ignore this email. This link will expire in 15 minutes.<br/>
                    If the button doesn't work, copy and paste this link into your browser: <br/>
                    <a href="{reset_link}" style="color: #4f46e5; text-decoration: none; word-break: break-all;">{reset_link}</a>
                </p>
                <br/>
                <p>Thank you,</p>
                <p>HR Platform Team</p>
            </body>
        </html>
        """

        text = f"""
        Hello,

        You requested a password reset for your HR Platform account.
        Please copy and paste the following link into your browser to reset your password:
        {reset_link}

        If you did not request this, please ignore this email. This link will expire in 15 minutes.

        Thank you,
        HR Platform Team
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.settings.emails_from_email or self.settings.smtp_user
        msg["To"] = email_to

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart/alternative is the preferred one.
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        
        msg.attach(part1)
        msg.attach(part2)

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.sendmail(msg["From"], [email_to], msg.as_string())
            logger.info(f"Password reset email sent to {email_to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {email_to}: {e}")
            return False
