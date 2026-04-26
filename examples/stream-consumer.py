#!/usr/bin/env python3
"""Connect to VoiceRefine WebSocket stream and print polished text as it arrives."""
import asyncio
import json
import websockets

async def main():
    uri = "ws://127.0.0.1:8765"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected. Waiting for polished text events...\n")
        async for message in ws:
            event = json.loads(message)
            if event.get("type") == "polished":
                print(f"[{event.get('timestamp', '?')}] ({event.get('duration_ms', 0)}ms)")
                print(f"  Raw:      {event.get('raw', '')}")
                print(f"  Polished: {event.get('text', '')}")
                print()

if __name__ == "__main__":
    asyncio.run(main())
