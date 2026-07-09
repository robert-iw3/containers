#!/usr/bin/env python

"""Build custom Splunk_TA_windows app"""

import tarfile
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from configparser import ConfigParser
from os import getcwd, path
from pathlib import Path, PurePath
from posixpath import join as posixjoin
from re import search
from tempfile import TemporaryDirectory


def exclusion(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Exclude self"""

    # exclude certain folders/files
    name = tarinfo.name
    pathname = PurePath(name)
    if search(
        r"/\.|\\\.|__pycache__|pyproject\.toml|requirements",
        name,
    ) or (len(pathname.parts) == 2 and tarinfo.isfile() and pathname.suffix != ".md"):
        return None

    app = pathname.parts[0]

    # reset file stats
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    if tarinfo.isfile():
        # remove execution permission
        tarinfo.mode = 0o644

        # except for scripts
        # tarinfo uses posix (not nt)
        if name.startswith(posixjoin(app, "bin")) and pathname.suffix in (
            ".py",
            ".ps1",
            ".cmd",
            ".bat",
        ):
            tarinfo.mode = 0o744
    if tarinfo.isdir():
        # remove write permission from group & world
        tarinfo.mode = 0o755

    return tarinfo


def main(input: str = "", cloud: bool = False):
    """
    :param input: Path to the downloaded Splunk app
    :param cloud: Create Splunk Cloud-compatible app
    """

    app_gz = input
    while not path.isfile(app_gz):
        print(
            "Download the latest [Splunk Add-on for Microsoft Windows]"
            "(https://splunkbase.splunk.com/app/742) with a Splunk.com account."
        )
        app_gz = input("Path to splunk-add-on-for-microsoft-windows_*.tgz: ")
    is_cloud = cloud

    app_dir, app_filename = path.split(app_gz)
    version = PurePath(app_filename).stem.split("_")[-1]
    new_gz = path.join(app_dir, f"Splunk_TA_windows_{version}.tgz")
    script_dir = path.dirname(__file__)

    with TemporaryDirectory() as tmpdir:
        app = ""
        with tarfile.open(app_gz) as tar:
            app = path.commonpath(tar.getnames())
            tar.extractall(path=tmpdir, filter="data")

        app_out_dir = path.join(tmpdir, app)
        print(f'Extracted "{app_gz}" to "{app_out_dir}"')

        if is_cloud is False:
            with tarfile.open(new_gz, "w:gz") as tar:
                tar.add(app_out_dir, filter=exclusion, arcname=app)
                tar.add(
                    path.join(script_dir, "eventtypes.conf"),
                    filter=exclusion,
                    arcname=posixjoin(app, "local", "eventtypes.conf"),
                )
                tar.add(
                    path.join(script_dir, "props.conf"),
                    filter=exclusion,
                    arcname=posixjoin(app, "local", "props.conf"),
                )
                tar.add(
                    path.join(script_dir, "tags.conf"),
                    filter=exclusion,
                    arcname=posixjoin(app, "local", "tags.conf"),
                )
                tar.add(
                    path.join(script_dir, "transforms.conf"),
                    filter=exclusion,
                    arcname=posixjoin(app, "local", "transforms.conf"),
                )
                tar.add(
                    path.join(script_dir, "inputs.conf"),
                    filter=exclusion,
                    arcname=posixjoin(app, "local", "inputs.conf"),
                )
                tar.add(
                    path.join(script_dir, "lookups"),
                    filter=exclusion,
                    arcname=posixjoin(app, "lookups"),
                )

            print(f'Created "{new_gz}"')

        else:
            new_app_id = "custom-Splunk_TA_windows"
            new_cloud_gz = path.join(app_dir, f"{new_app_id}_{version}.tgz")

            app_conf_path = path.join(
                app_out_dir,
                "default",
                "app.conf",
            )
            app_conf = ConfigParser()
            app_conf.read(app_conf_path)
            app_conf["launcher"]["author"] = "custom"
            app_conf["package"]["check_for_updates"] = "false"
            app_conf["package"]["id"] = new_app_id
            app_conf["id"] = {}
            app_conf["id"]["name"] = new_app_id
            app_conf["id"]["version"] = app_conf["launcher"]["version"]

            new_app_conf_path = path.join(
                app_out_dir,
                "local",
                "app.conf",
            )

            Path(path.dirname(new_app_conf_path)).mkdir(mode=0o755, parents=True)
            with open(new_app_conf_path, "w", encoding="utf-8") as configfile:
                app_conf.write(configfile)

            with tarfile.open(new_cloud_gz, "w:gz") as tar:
                tar.add(
                    path.join(new_app_conf_path),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "app.conf"),
                )
                tar.add(
                    path.join(script_dir, "eventtypes.conf"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "eventtypes.conf"),
                )
                tar.add(
                    path.join(script_dir, "props.conf"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "props.conf"),
                )
                tar.add(
                    path.join(script_dir, "tags.conf"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "tags.conf"),
                )
                tar.add(
                    path.join(script_dir, "transforms.conf"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "transforms.conf"),
                )
                tar.add(
                    path.join(script_dir, "inputs.conf"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "default", "inputs.conf"),
                )
                tar.add(
                    path.join(script_dir, "lookups"),
                    filter=exclusion,
                    arcname=posixjoin(new_app_id, "lookups"),
                )

            print(f'Created "{new_cloud_gz}"')


if __name__ == "__main__":
    files = Path(getcwd()).glob("splunk-add-on-for-microsoft-windows_*.tgz")
    app_paths = []
    for i in files:
        app_paths.append(i)
    app_path = app_paths[0] if len(app_paths) >= 1 else ""

    parser = ArgumentParser(
        description="Create Splunk app package.",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to Splunk app.",
        default=app_path,
        type=Path,
    )
    parser.add_argument(
        "--cloud",
        "-c",
        help="Create Splunk Cloud-compatible app.",
        action="store_true",
    )

    args = parser.parse_args()
    main(**vars(args))
