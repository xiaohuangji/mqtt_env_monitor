"""Start a lightweight local MQTT broker for project verification."""

from __future__ import annotations

import argparse
import asyncio

from amqtt.broker import Broker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a local MQTT broker.")
    parser.add_argument("--host", default="127.0.0.1", help="Broker bind host.")
    parser.add_argument("--port", type=int, default=1883, help="Broker bind port.")
    return parser.parse_args()


async def run_broker(host: str, port: int) -> None:
    config = {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"{host}:{port}",
                "max_connections": 100,
            }
        },
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True,
            },
        },
    }

    broker = Broker(config)
    await broker.start()
    print(f"MQTT broker started at {host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run_broker(args.host, args.port))
    except KeyboardInterrupt:
        print("\nMQTT broker stopped.")


if __name__ == "__main__":
    main()
