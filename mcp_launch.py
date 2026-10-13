"""Start palantir-mcp with credentials from ./.env (PALANTIR_FOUNDRY_HOST/TOKEN -> FOUNDRY_HOST/TOKEN). Run by .mcp.json."""
import os, subprocess, sys
from pathlib import Path

kv = dict(l.strip().split("=", 1) for l in open(Path(__file__).with_name(".env")) if "=" in l)
host = kv["PALANTIR_FOUNDRY_HOST"].strip().removeprefix("https://").rstrip("/")
env = dict(os.environ, FOUNDRY_HOST=host, FOUNDRY_TOKEN=kv["PALANTIR_FOUNDRY_TOKEN"].strip())
sys.exit(subprocess.call(["npx.cmd", "-y", "palantir-mcp", "--foundry-api-url", f"https://{host}"], env=env))
