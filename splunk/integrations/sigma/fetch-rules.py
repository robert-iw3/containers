#!/usr/bin/env python3

"""Fetch Sigma detection rules from reputable sources. Standard library only.

Pulls SigmaHQ's published release assets rather than cloning. A release is a
versioned, hash-checkable artifact; a clone is whatever master held that
minute, needs git, and cannot be reproduced later. Provenance for everything
fetched is written to provenance.json.

The air-gapped path is the point of --make-bundle and --from-bundle: fetch
and verify on a connected host, carry one file in, install it inside with no
network. Nothing in the install path reaches the network.

Only SigmaHQ is a default source. Other repositories are real and widely
used but adding one is a supply-chain decision, so each is opt-in by name
and recorded with its commit and hash. An accredited environment has to be
able to say where a rule came from.

  fetch-rules.py --list
  fetch-rules.py --package core --out ./rules
  fetch-rules.py --package all --make-bundle sigma-bundle.tar.gz
  fetch-rules.py --from-bundle sigma-bundle.tar.gz --out ./rules
  fetch-rules.py --source dfir-report --out ./rules
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

UA = {"User-Agent": "sigma-fetch-rules/1.0", "Accept": "application/vnd.github+json"}

# SigmaHQ release assets. core is the curated baseline; all is everything
# including emerging threats and threat hunting.
SIGMAHQ_PACKAGES = {
    "core": "sigma_core.zip",
    "core+": "sigma_core+.zip",
    "core++": "sigma_core++.zip",
    "all": "sigma_all_rules.zip",
    "emerging-threats": "sigma_emerging_threats_addon.zip",
}

# Extra sources, each opt-in by name. Fetched as a tarball of a named ref so
# the exact commit is recorded.
EXTRA_SOURCES = {
    "dfir-report": {
        "repo": "The-DFIR-Report/Sigma-Rules",
        "ref": "main",
        "subdir": "",
        "note": "The DFIR Report's rules, derived from their published intrusion analyses.",
    },
    "mdecrevoisier": {
        "repo": "mdecrevoisier/SIGMA-detection-rules",
        "ref": "master",
        "subdir": "",
        "note": "Community rules covering Windows audit sources not in SigmaHQ core.",
    },
}

GITHUB_API = "https://api.github.com"


def fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_json(url: str, timeout: int = 60):
    return json.loads(fetch(url, timeout).decode("utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_members_zip(zf: zipfile.ZipFile):
    """Reject any entry that would write outside the extraction directory."""
    bad = []
    for name in zf.namelist():
        if name.startswith("/") or ".." in Path(name).parts:
            bad.append(name)
    if bad:
        raise ValueError(f"archive contains unsafe paths: {bad[:5]}")
    return zf.namelist()


def safe_members_tar(tf: tarfile.TarFile):
    bad = []
    for m in tf.getmembers():
        if m.name.startswith("/") or ".." in Path(m.name).parts:
            bad.append(m.name)
        if m.issym() or m.islnk():
            bad.append(f"{m.name} (link)")
    if bad:
        raise ValueError(f"archive contains unsafe paths: {bad[:5]}")
    return tf.getmembers()


def count_rules(root: Path) -> int:
    return sum(1 for _ in root.rglob("*.yml"))


# ------------------------------------------------------------- SigmaHQ

def sigmahq_release(tag: str = None):
    if tag:
        url = f"{GITHUB_API}/repos/SigmaHQ/sigma/releases/tags/{tag}"
    else:
        url = f"{GITHUB_API}/repos/SigmaHQ/sigma/releases/latest"
    return fetch_json(url)


def cmd_list(args):
    rel = sigmahq_release(args.release)
    print(f"SigmaHQ/sigma release {rel['tag_name']}  published {rel['published_at']}")
    print(f"{'package':<20} {'asset':<36} {'size':>12}")
    assets = {a["name"]: a for a in rel["assets"]}
    for pkg, asset_name in SIGMAHQ_PACKAGES.items():
        a = assets.get(asset_name)
        if a:
            print(f"{pkg:<20} {asset_name:<36} {a['size']:>12,}")
        else:
            print(f"{pkg:<20} {asset_name:<36} {'(absent)':>12}")
    print()
    print("extra sources, opt-in with --source:")
    for name, meta in EXTRA_SOURCES.items():
        print(f"  {name:<16} {meta['repo']}@{meta['ref']}")
        print(f"  {'':<16} {meta['note']}")
    return 0


def download_sigmahq(package: str, tag: str, dest_dir: Path):
    """Download and verify one SigmaHQ release asset. Returns provenance."""
    asset_name = SIGMAHQ_PACKAGES[package]
    rel = sigmahq_release(tag)
    assets = {a["name"]: a for a in rel["assets"]}
    if asset_name not in assets:
        raise SystemExit(f"release {rel['tag_name']} has no asset {asset_name}")
    asset = assets[asset_name]
    print(f"  downloading {asset_name} ({asset['size']:,} bytes) "
          f"from release {rel['tag_name']}")
    data = fetch(asset["browser_download_url"], timeout=300)
    if len(data) != asset["size"]:
        raise SystemExit(f"size mismatch: got {len(data)}, expected {asset['size']}")
    digest = sha256_bytes(data)
    dest_dir.mkdir(parents=True, exist_ok=True)
    blob = dest_dir / asset_name
    blob.write_bytes(data)
    print(f"  sha256 {digest}")
    return {
        "source": "SigmaHQ/sigma",
        "kind": "release-asset",
        "release": rel["tag_name"],
        "published_at": rel["published_at"],
        "package": package,
        "asset": asset_name,
        "url": asset["browser_download_url"],
        "size": asset["size"],
        "sha256": digest,
        "local_blob": str(blob),
    }


def download_extra(name: str, dest_dir: Path):
    meta = EXTRA_SOURCES[name]
    repo, ref = meta["repo"], meta["ref"]
    commit = fetch_json(f"{GITHUB_API}/repos/{repo}/commits/{ref}")
    sha = commit["sha"]
    url = f"{GITHUB_API}/repos/{repo}/tarball/{sha}"
    print(f"  downloading {repo}@{sha[:12]}")
    data = fetch(url, timeout=300)
    digest = sha256_bytes(data)
    dest_dir.mkdir(parents=True, exist_ok=True)
    blob = dest_dir / f"{name}-{sha[:12]}.tar.gz"
    blob.write_bytes(data)
    print(f"  sha256 {digest}")
    return {
        "source": repo,
        "kind": "git-tarball",
        "ref": ref,
        "commit": sha,
        "committed_at": commit["commit"]["committer"]["date"],
        "url": url,
        "size": len(data),
        "sha256": digest,
        "note": meta["note"],
        "local_blob": str(blob),
    }


# --------------------------------------------------------------- extract

def extract_blob(prov: dict, out: Path) -> int:
    """Extract one downloaded artifact into out/, flattening the archive's
    own top-level wrapper directory. Returns the rule count."""
    blob = Path(prov["local_blob"])
    target = out / re.sub(r"[^A-Za-z0-9_.-]", "_", prov["source"])
    if prov.get("package"):
        target = target / prov["package"]
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        if blob.suffix == ".zip":
            with zipfile.ZipFile(blob) as zf:
                safe_members_zip(zf)
                zf.extractall(tmpdir)
        else:
            with tarfile.open(blob, "r:gz") as tf:
                members = safe_members_tar(tf)
                tf.extractall(tmpdir, members=members)
        # A GitHub tarball wraps everything in one directory; a SigmaHQ zip
        # does not. Flatten only when there is exactly one wrapper.
        entries = [p for p in tmpdir.iterdir()]
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmpdir
        for item in root.iterdir():
            dst = target / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

    n = count_rules(target)
    print(f"  extracted {n:,} rules to {target}")
    return n


# ---------------------------------------------------------------- bundles

def make_bundle(provs: list, staging: Path, bundle_path: Path):
    """Pack verified artifacts plus provenance into one transferable file."""
    manifest = {"created_at": time.time(), "artifacts": provs,
                "bundle_format": 1}
    (staging / "provenance.json").write_text(json.dumps(manifest, indent=1),
                                             encoding="utf-8")
    with tarfile.open(bundle_path, "w:gz") as tf:
        for p in sorted(staging.iterdir()):
            tf.add(p, arcname=p.name)
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    (bundle_path.parent / (bundle_path.name + ".sha256")).write_text(
        f"{digest}  {bundle_path.name}\n", encoding="utf-8")
    print(f"\nbundle: {bundle_path}")
    print(f"sha256: {digest}")
    print(f"sidecar: {bundle_path}.sha256")
    print("\nCarry both files in. Verify on the far side with:")
    print(f"  sha256sum -c {bundle_path.name}.sha256")
    return digest


def cmd_from_bundle(args):
    bundle = Path(args.from_bundle)
    if not bundle.exists():
        raise SystemExit(f"bundle not found: {bundle}")
    sidecar = Path(str(bundle) + ".sha256")
    actual = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if sidecar.exists():
        expected = sidecar.read_text(encoding="utf-8").split()[0]
        if expected != actual:
            raise SystemExit(f"bundle checksum mismatch\n  expected {expected}\n"
                             f"  actual   {actual}")
        print(f"bundle checksum verified: {actual}")
    else:
        print(f"WARNING: no {sidecar.name} beside the bundle; "
              f"cannot verify integrity")
        print(f"  bundle sha256: {actual}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        with tarfile.open(bundle, "r:gz") as tf:
            members = safe_members_tar(tf)
            tf.extractall(tmpdir, members=members)
        prov_file = tmpdir / "provenance.json"
        if not prov_file.exists():
            raise SystemExit("bundle has no provenance.json; refusing to install")
        manifest = json.loads(prov_file.read_text(encoding="utf-8"))

        total = 0
        for prov in manifest["artifacts"]:
            blob = tmpdir / Path(prov["local_blob"]).name
            if not blob.exists():
                print(f"  SKIP {prov['source']}: {blob.name} missing from bundle")
                continue
            digest = sha256_bytes(blob.read_bytes())
            if digest != prov["sha256"]:
                raise SystemExit(f"artifact checksum mismatch for {blob.name}\n"
                                 f"  expected {prov['sha256']}\n  actual   {digest}")
            print(f"  {blob.name}: sha256 verified")
            prov = dict(prov, local_blob=str(blob))
            total += extract_blob(prov, out)

        (out / "provenance.json").write_text(json.dumps(manifest, indent=1),
                                             encoding="utf-8")
    print(f"\ninstalled {total:,} rules to {out} with no network access")
    return 0


# ------------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="./rules", help="Where to extract rules")
    ap.add_argument("--package", action="append", default=None,
                    choices=sorted(SIGMAHQ_PACKAGES),
                    help="SigmaHQ release package; repeatable. Default: core")
    ap.add_argument("--source", action="append", default=None,
                    choices=sorted(EXTRA_SOURCES),
                    help="Additional reputable source; repeatable, opt-in")
    ap.add_argument("--release", default=None,
                    help="SigmaHQ release tag (default: latest)")
    ap.add_argument("--no-sigmahq", action="store_true",
                    help="Skip SigmaHQ; only fetch --source repositories")
    ap.add_argument("--list", action="store_true",
                    help="Show available packages and sources, then exit")
    ap.add_argument("--make-bundle", default=None, metavar="PATH",
                    help="Write a transferable bundle instead of extracting. "
                         "For moving rules to an air-gapped environment.")
    ap.add_argument("--from-bundle", default=None, metavar="PATH",
                    help="Install from a bundle. Never touches the network.")
    ap.add_argument("--keep-blobs", action="store_true",
                    help="Keep the downloaded archives beside the rules")
    args = ap.parse_args(argv[1:])

    if args.from_bundle:
        return cmd_from_bundle(args)

    if args.list:
        return cmd_list(args)

    packages = args.package or (["core"] if not args.no_sigmahq else [])
    if args.no_sigmahq:
        packages = []
    sources = args.source or []
    if not packages and not sources:
        raise SystemExit("nothing to fetch: pass --package and/or --source")

    staging = Path(tempfile.mkdtemp(prefix="sigma-fetch-"))
    provs = []
    try:
        for pkg in packages:
            print(f"SigmaHQ package '{pkg}':")
            provs.append(download_sigmahq(pkg, args.release, staging))
        for name in sources:
            print(f"source '{name}':")
            provs.append(download_extra(name, staging))

        if args.make_bundle:
            bundle = Path(args.make_bundle)
            bundle.parent.mkdir(parents=True, exist_ok=True)
            make_bundle(provs, staging, bundle)
            return 0

        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        total = 0
        print()
        for prov in provs:
            print(f"{prov['source']}:")
            total += extract_blob(prov, out)
            if args.keep_blobs:
                shutil.copy2(prov["local_blob"], out / Path(prov["local_blob"]).name)

        manifest = {"fetched_at": time.time(), "artifacts": provs,
                    "total_rules": total}
        (out / "provenance.json").write_text(json.dumps(manifest, indent=1),
                                             encoding="utf-8")
        print(f"\n{total:,} rules in {out}")
        print(f"provenance: {out / 'provenance.json'}")
    finally:
        if not args.keep_blobs:
            shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except urllib.error.URLError as e:
        sys.exit(f"network error: {e}\n"
                 f"If this host has no internet, use --from-bundle with a "
                 f"bundle made on a connected host.")
