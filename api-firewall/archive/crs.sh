#!/bin/sh

<<comment

The OWASP CRS is a set of generic attack detection rules for use with ModSecurity
or compatible web application firewalls. The CRS aims to protect web applications
from a wide range of attacks, including the OWASP Top Ten, with a minimum of false alerts.

https://github.com/coreruleset/coreruleset

comment

CRS_URL=https://github.com/coreruleset/coreruleset/archive/refs/tags/v4.18.0.tar.gz
CRS_FILE=v4.18.0.tar.gz
CRS_DIR=./crs

test -f $(CRS_FILE) || wget $(CRS_URL) -O $(CRS_FILE)
    if [ ! -d "$(CRS_DIR)" ]; then \
    		mkdir $(CRS_DIR); \
    		tar -xzvf $(CRS_FILE) --strip-components 1 -C $(CRS_DIR); \
    fi