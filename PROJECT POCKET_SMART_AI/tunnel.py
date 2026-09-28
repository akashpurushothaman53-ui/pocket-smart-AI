"""
tunnel.py - Auto-Reconnecting Public Tunnel for PocketSmart AI
Keeps a public HTTPS tunnel active and saves the URL to public_url.txt.
"""

import subprocess
import time
import re
import sys
import os

print("Starting auto-reconnecting public tunnel for PocketSmart AI (port 8000)...")

while True:
    try:
        proc = subprocess.Popen(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=15",
                "-o", "ServerAliveCountMax=6",
                "-R", "80:127.0.0.1:8000",
                "nokey@localhost.run"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if ".lhr.life" in line and "https://" in line:
                match = re.search(r"https://[a-zA-Z0-9.-]+\.lhr\.life", line)
                if match:
                    url = match.group(0)
                    with open("public_url.txt", "w") as f:
                        f.write(url.strip())
                    print("\n" + "=" * 55)
                    print(f"  POCKETSMART AI PUBLIC LIVE URL: {url}")
                    print("=" * 55 + "\n")
                    sys.stdout.flush()

        proc.wait()
    except Exception as e:
        print(f"Tunnel connection interrupted: {e}")

    print("Reconnecting tunnel in 3 seconds...")
    time.sleep(3)
