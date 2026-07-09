#!/usr/bin/env python3

import json
import sys
import platform
from pathlib import Path


def check_os():
    """Check if the operating system is Mac OS."""
    if platform.system() != "Darwin":
        print("Error: This setup script is only supported on Mac OS.")
        print(f"Current operating system: {platform.system()}")
        sys.exit(1)


def get_config_path():
    """Get the path to the Claude Desktop config file."""
    home = Path.home()
    return (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )


def setup_claude_desktop():
    """Set up Claude Desktop configuration for the current project."""
    check_os()

    config_path = get_config_path()

    if not config_path.exists():
        print(f"Error: Claude Desktop config not found at {config_path}")
        print("Please make sure Claude Desktop is installed and configured.")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        current_dir = Path(__file__).parent.parent.absolute()
        src_dir = current_dir / "bridge"

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        config["mcpServers"]["binary_ninja_mcp"] = {
            "command": str(Path.cwd() / ".venv" / "bin" / "python"),
            "args": [str(src_dir / "binja_mcp_bridge.py")],
        }

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print("Successfully updated Claude Desktop configuration.")

    except Exception as e:
        print(f"Error updating configuration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_claude_desktop()
