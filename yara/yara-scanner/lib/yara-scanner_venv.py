"""
venv autodetect
"""

import os
import sys


def venv_setup(yara-scanner_venv_site: str) -> bool:
    """
    venv setup
    """
    if os.path.exists(yara-scanner_venv_site):
        sys.path.insert(0, yara-scanner_venv_site)
        return True
    return False


# venv detection
def venv_check(yara-scanner_script_name: str) -> None:
    """
    venv check
    """
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    yara-scanner_base_path = os.path.dirname(os.path.realpath(yara-scanner_script_name))
    yara-scanner_venv_path = f"{yara-scanner_base_path}/venv"
    yara-scanner_venv_site = (
        f"{yara-scanner_venv_path}/lib/python{python_version}/site-packages"
    )

    if not os.environ["PATH"].startswith(yara-scanner_venv_path):
        venv_ready = venv_setup(yara-scanner_venv_site)
        if not venv_ready:
            print(f"{yara-scanner_venv_path} not found")
            print("Consider using ./deploy.sh to deploy venv")
