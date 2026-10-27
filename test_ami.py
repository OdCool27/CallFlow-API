"""Explicit, read-only AMI connectivity probe; never runs during pytest collection."""
import asyncio

from app.ami import encode_action, read_frame
from app.config import settings


async def probe():
    if not settings.ami_secret:
        raise SystemExit("Set AMI_SECRET in .env or the environment first")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(settings.ami_host, settings.ami_port), settings.ami_timeout)
    try:
        banner = await asyncio.wait_for(reader.readline(), settings.ami_timeout)
        print(banner.decode().strip())
        writer.write(encode_action("Login", Username=settings.ami_username, Secret=settings.ami_secret,
                                   Events="off", ActionID="probe"))
        await writer.drain()
        response = await asyncio.wait_for(read_frame(reader), settings.ami_timeout)
        if response.get("Response") != "Success":
            raise SystemExit("AMI authentication failed")
        print("AMI authentication succeeded")
        writer.write(encode_action("Logoff"))
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(probe())
