from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class EmailConfig:
    recipient: str
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    sender: str
    use_tls: bool = True

    def validate(self) -> tuple[bool, str]:
        if not self.recipient or "@" not in self.recipient:
            return False, "Recipient email address is invalid."
        if not self.smtp_host:
            return False, "SMTP host is required."
        if self.smtp_port <= 0 or self.smtp_port > 65535:
            return False, "SMTP port must be between 1 and 65535."
        if not self.username:
            return False, "SMTP username is required."
        if not self.password:
            return False, "SMTP password/app password is required."
        if not self.sender or "@" not in self.sender:
            return False, "Sender email address is invalid."
        return True, ""


class EmailNotifier:
    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send_alarm_alert(self, alarm_message: str, system_state: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Smart Drawer Anti-Theft Alarm"
        message["From"] = self.config.sender
        message["To"] = self.config.recipient
        message.set_content(
            "\n".join(
                [
                    "Smart Drawer Anti-Theft System detected an alarm.",
                    "",
                    f"System state: {system_state}",
                    f"Alarm message: {alarm_message}",
                    "",
                    "Only one email is sent for each alarm session.",
                ]
            )
        )

        if self.config.use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, context=context, timeout=15) as server:
                server.login(self.config.username, self.config.password)
                server.send_message(message)
        else:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(self.config.username, self.config.password)
                server.send_message(message)
