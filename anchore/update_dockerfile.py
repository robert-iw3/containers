#!/usr/bin/env python3

import requests
import re
import sys
import os

def fetch_latest_version(repo):
    """Fetch the latest release tag from GitHub API for the given repo."""
    url = f"https://api.github.com/repos/anchore/{repo}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    tag = response.json()["tag_name"]
    return tag.lstrip("v")

def update_dockerfile(filename):
    """Update the Dockerfile with latest Syft and Grype versions."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Dockerfile not found: {filename}")

    # Fetch latest versions
    syft_ver = fetch_latest_version("syft")
    grype_ver = fetch_latest_version("grype")

    print(f"Updating Syft to version: {syft_ver}")
    print(f"Updating Grype to version: {grype_ver}")

    # Read the file
    with open(filename, "r") as f:
        content = f.read()

    # Update ENV vars (match lines starting with ENV and the var name)
    content = re.sub(
        r"(^ENV SYFT_VER=)[^ \n]+",
        rf"\1{syft_ver}",
        content,
        flags=re.MULTILINE
    )
    content = re.sub(
        r"(^ENV GRYPE_VER=)[^ \n]+",
        rf"\1{grype_ver}",
        content,
        flags=re.MULTILINE
    )

    # Update the label (match the schema-version value)
    content = re.sub(
        r"(schema-version=')Grype [^,]+,\s*Syft [^']*(')",
        rf"\1Grype {grype_ver}, Syft {syft_ver}\2",
        content
    )

    # Write back
    with open(filename, "w") as f:
        f.write(content)

    print("Dockerfile updated successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path_to_dockerfile>")
        sys.exit(1)
    try:
        update_dockerfile(sys.argv[1])
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)