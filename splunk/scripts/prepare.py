#!/usr/bin/env python

"""Prepare setup files for Splunk Enterprise installation and save them into splunk-setup-all.tar.gz"""

import tarfile
from os import chdir, path
from pathlib import Path, PurePath
from re import search
from tempfile import TemporaryDirectory

from build import main as build_app

chdir_path = path.dirname(__file__)
chdir(chdir_path)


def exclusion(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Exclude self"""

    # exclude certain folders/files
    pathname = tarinfo.name
    if search(
        r"/\.|\\\.|__pycache__|pyproject\.toml|requirements|prepare\.py|splunk-setup-all\.tar\.gz",
        pathname,
    ):
        return None

    # reset file stats
    # based on https://splunkbase.splunk.com/app/833
    tarinfo.uid = 1001
    tarinfo.gid = 123
    tarinfo.uname = tarinfo.gname = ""
    if tarinfo.isfile():
        # remove execution permission
        tarinfo.mode = 0o644

        # except for shell scripts
        if tarinfo.name.endswith(".sh"):
            tarinfo.mode = 0o744
    if tarinfo.isdir():
        # remove write permission from group & world
        tarinfo.mode = 0o755

    return tarinfo


def glob(pattern: str, out_path: str = "") -> Path | str:
    filelist = list(Path(".").glob(pattern))
    pattern_ext = PurePath(pattern).suffix
    if len(filelist) >= 1:
        return filelist[0]

    if path.isfile(out_path) and (
        len(pattern_ext) <= 0
        or (len(pattern_ext) >= 1 and PurePath(out_path).suffix == pattern_ext)
    ):
        return out_path

    out_path = path.abspath(Path(input(f"Path to {pattern}: ")))

    if not path.isfile(out_path):
        print(f'"{out_path}" is not a file or does not exist.')
    elif len(pattern_ext) >= 1 and PurePath(out_path).suffix != pattern_ext:
        print(f'"{out_path}" is not a *{pattern_ext} file.')

    return glob(pattern, out_path)


enterprise_gz = glob("splunk-*-linux-amd64.tgz")
output_gz = path.join(path.dirname(enterprise_gz), "splunk-setup-all.tar.gz")
host_key = glob("splunk_host_ed25519_key")
splunk_cert_key = glob("splunk-cert.key", "certs")
splunk_cert_pem = glob("splunk-cert.pem", "certs")
splunk_cert_web_pem = glob("splunk-cert-web.pem", "certs")
deployment_apps = ["1-deploymentserver", "1-indexserver", "100_splunkcloud"]

with TemporaryDirectory() as tmpdir:
    built_apps = {}
    for app in deployment_apps:
        app_path = path.join("..", "deployment-apps", app)
        if path.isdir(app_path):
            built_apps.add(
                build_app(
                    directory=app_path,
                    output=tmpdir,
                )
            )
    with tarfile.open(output_gz, "w:gz") as tar:
        tar.add(".", filter=exclusion)
        tar.add(
            path.join("..", "enterprise_root_cacert.crt"),
            arcname="./enterprise_root_cacert.crt",
            filter=exclusion,
        )
        tar.add(
            path.join("..", "enterprise_intermediate_cacert.crt"),
            arcname="./enterprise_intermediate_cacert.crt",
            filter=exclusion,
        )
        tar.add(
            path.join(
                "..",
                "deployment-apps",
                "100_splunkcloud",
                "default",
                "100_splunkcloud_root_cacert.crt",
            ),
            arcname="./100_splunkcloud_root_cacert.crt",
            filter=exclusion,
        )
        tar.add(
            path.join(
                "..",
                "deployment-apps",
                "100_splunkcloud",
                "default",
                "100_splunkcloud_intermediate_cacert.crt",
            ),
            arcname="./100_splunkcloud_intermediate_cacert.crt",
            filter=exclusion,
        )
        for built_app in built_apps:
            tar.add(
                built_app,
                arcname=path.basename(built_app),
                filter=exclusion,
            )

print(f'Created "{output_gz}"')
