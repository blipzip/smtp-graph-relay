import asyncio
import os
import ssl
from aiosmtpd.controller import Controller
from email.parser import BytesParser
from email.header import decode_header
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import aiohttp

# =========================
# CONFIG
# =========================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8587

SENDER = os.environ["SENDER"]

ALLOWED_DOMAINS = os.environ.get("ALLOWED_DOMAINS", "").split(",")
ALLOWED_ADDRESSES = os.environ.get("ALLOWED_ADDRESSES", "").split(",")

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["SECRET_ID"]

CERT_FILE = os.environ.get("CERT_FILE")
KEY_FILE = os.environ.get("KEY_FILE")

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_SEND_URL = f"https://graph.microsoft.com/v1.0/users/{SENDER}/sendMail"


# =========================
# GRAPH CLIENT (ASYNC)
# =========================
def allowed_recipient(addr, allowed):
    addr = addr.lower()
    
    if addr in allowed:
        return True

    domain = addr.split("@")[-1]

    if domain in allowed:
        return True

    return False

def filter_recipients(addresses) -> list | None:
    return [{"emailAddress": {"address": addr}} for addr in addresses if allowed_recipient(addr, ALLOWED_ADDRESSES)]



def get_subject(msg) -> str:
    raw = msg.get("Subject", "")

    decoded_parts = decode_header(raw)
    subject = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            subject += part.decode(encoding or "utf-8", errors="ignore")
        else:
            subject += part

    return subject


async def get_graph_token(session: aiohttp.ClientSession) -> str:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }

    async with session.post(TOKEN_URL, data=data) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Token error: {await resp.text()}")

        payload = await resp.json()
        return payload["access_token"]
def generate_payload(body: str, subject: str, to_addrs: list | None, cc_addrs: list | None, bcc_addrs: list | None) -> dict:
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
            },
            "saveToSentItems": False,
        }

        if to_addrs:
            payload["message"]["toRecipients"] = to_addrs

        if cc_addrs:
            payload["message"]["ccRecipients"] = cc_addrs
        
        if bcc_addrs:
            payload["message"]["bccRecipients"] = bcc_addrs
        
        return payload

async def send_mail(payload: dict):
    async with aiohttp.ClientSession() as session:
        token = await get_graph_token(session)

        async with session.post(
            GRAPH_SEND_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            if resp.status not in (200, 202):
                raise RuntimeError(
                    f"Graph send failed: {resp.status} {await resp.text()}"
                )


# =========================
# SMTP HANDLER
# =========================
class MailHandler:
    async def handle_DATA(self, server, session, envelope):
        msg = BytesParser(policy=policy.default).parsebytes(envelope.original_content)
        subject = get_subject(msg)

        if msg.is_multipart():
            parts = []
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)  # can be bytes or None
                    if isinstance(payload, bytes):
                        text = payload.decode(errors="ignore")
                    elif isinstance(payload, str):
                        text = payload
                    else:
                        text = ""
                    parts.append(text)
            body = "\n".join(parts)
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode(errors="ignore")
            elif isinstance(payload, str):
                body = payload
            else:
                body = ""

        print(f"Received mail - {subject} — forwarding via Graph")
        to_addrs = filter_recipients(getaddresses(msg.get_all("to", [])))
        cc_addrs = filter_recipients(getaddresses(msg.get_all("cc", [])))
        bcc_addrs = filter_recipients(getaddresses(msg.get_all("bcc", [])))

        payload = generate_payload(body, subject, to_addrs, cc_addrs, bcc_addrs)
        await send_mail(payload)

        return "250 Message accepted for delivery"


async def main():
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    controller = Controller(
        MailHandler(),
        hostname=LISTEN_HOST,
        port=LISTEN_PORT,
        tls_context=ssl_ctx,
        require_starttls=True,

    )

    controller.start()
    print(f"SMTP server listening on {LISTEN_HOST}:{LISTEN_PORT}")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
