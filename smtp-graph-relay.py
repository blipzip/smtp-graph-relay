import asyncio
import os
import ssl
from aiosmtpd.controller import Controller
from email.parser import BytesParser
from email.policy import default
import aiohttp

# =========================
# CONFIG
# =========================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8587

SENDER = os.environ["SENDER"]
RECIPIENT = os.environ["RECIPIENT"]

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


async def send_mail(body: str):
    async with aiohttp.ClientSession() as session:
        token = await get_graph_token(session)

        payload = {
            "message": {
                "subject": "Forwarded message",
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
                "toRecipients": [{"emailAddress": {"address": RECIPIENT}}],
            },
            "saveToSentItems": False,
        }

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
        msg = BytesParser(policy=default).parsebytes(envelope.original_content)

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

        print("📨 Received mail — forwarding via Graph")

        await send_mail(body)

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
    print(f"✅ SMTP server listening on {LISTEN_HOST}:{LISTEN_PORT}")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
