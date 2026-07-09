#!/bin/bash
set -e

# Colors
ORANGE="\e[1;33m"
ENDCOLOR="\e[0m"

# Color print function
print() {
    echo -e "${ORANGE}${1}${ENDCOLOR}"
}

# Check arch
check_arch() {
    if command -v arch ; then
        ARCH=$(arch)
    else
        ARCH=$(cat /proc/sys/kernel/arch)
    fi
}

# Parse args
while [[ $# -gt 0 ]]; do
case $1 in
    --with-signatures)
        WITH_SIGNATURES="$1"
        shift
        ;;
    --with-addons)
        WITH_ADDONS="$1"
        shift
        ;;
    --with-source)
        WITH_SOURCE="$1"
        shift
        ;;
    --with-test)
        WITH_TEST="$1"
        shift
        ;;
    -h|--help)
        print "yara-scanner: build script"
        echo ""
        echo "Usage: ./build.sh [options]"
        echo ""
        echo "--with-addons        Include addons"
        echo "--with-signatures    Include signature-base"
        echo "--with-source        Include source .py files"
        echo "--with-test          Include test samples"
        exit 0
        ;;
    -*|--*)
        echo "Unknown option: $1"
        exit 1
        ;;
    *)
        continue
        ;;
    esac
done

# Check version
VERSION=$(
    grep ^__version lib/yara-scanner_logger.py \
    | grep -oP "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"
)

# Detect musl
if [[ -e /lib/ld-musl-aarch64.so.1 ]]; then
    VERSION="${VERSION}-musl"
fi

# Build
check_arch
print "yara-scanner: build script"
print "Building yara-scanner"
echo "${VERSION}-${ARCH} 🚀"

print "Build (1/8): venv"
if [[ ! -e venv/pyvenv.cfg ]]; then
    ./deploy.sh
fi

source venv/bin/activate

print "Build (2/8): upgrade tools"
pip install pyinstaller black ruff

print "Build (3/8): formatting"
black --quiet ./*.py ./lib/*.py

print "Build (4/8): linting"
ruff -v ./*.py ./lib/*.py

rm -rf build/
rm -rf dist/

# Disable venv_check
sed -i \
    -e 's/^venv_check/\#venv_check/g;' \
    -e 's/^from\ lib.venv/\#from\ lib.venv/g;' \
    ./*.py lib/*.py

# PyInstaller
print "Build (5/8): pyinstaller yara-scanner"
pyinstaller -F yara-scanner.py

print "Build (6/8): pyinstaller upgrader"
pyinstaller -F upgrader.py

print "Build (7/8): pyinstaller client"
pyinstaller -F client.py

# Enable venv_check back
sed -i \
    -e 's/^\#\ venv_check/venv_check/g;' \
    -e 's/^\#venv_check/venv_check/g;' \
    -e 's/^\#\ from\ lib.venv/from\ lib.venv/g;' \
    -e 's/^\#from\ lib.venv/from\ lib.venv/g;' \
    ./*.py lib/*.py

# Create packages
print "Build (8/8): packaging"

rm -rf yara-scanner*"${ARCH}"*
cp -r config dist/
cp README.md dist/
cp LICENSE dist/
cp CHANGELOG dist/

# Include addons
if [[ "${WITH_ADDONS}" && -d addons ]]; then
    cp -r addons dist/
    rm -rf dist/addons/img
fi

# Include signature-base
if [[ "${WITH_SIGNATURES}" && -d signature-base ]]; then
    cp -r signature-base dist/
fi

# Include source files
if [[ "${WITH_SOURCE}" ]]; then
    cp ./*.py dist/
    mkdir dist/lib
    cp lib/*.py dist/lib/
    cp venv.sh dist/
    cp build.sh dist/
    cp requirements.txt dist/
fi

# Include test samples
if [[ "${WITH_TEST}" ]]; then
    cp -r test dist/
fi

mv dist yara-scanner-"${VERSION}"-"${ARCH}"
if command -v zip &>/dev/null ; then
    zip -r -9 -T yara-scanner-"${VERSION}"-"${ARCH}".zip yara-scanner-"${VERSION}"-"${ARCH}"
fi
if command -v tar &>/dev/null && command -v gzip &>/dev/null ; then
    tar -I "gzip -9" -cvf yara-scanner-"${VERSION}"-"${ARCH}".tar.gz yara-scanner-"${VERSION}"-"${ARCH}"
fi
mv yara-scanner-"${VERSION}"-"${ARCH}" dist

print "Build complete 🎉"
