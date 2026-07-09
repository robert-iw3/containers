#!/usr/bin/env python
import sys
import os
from copy import deepcopy
path = os.path.dirname(os.path.abspath(__file__))
bin_path = os.path.join(path, 'ta_tenable')
if bin_path not in sys.path:
    sys.path.append(bin_path)

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from tenable.sc import TenableSC  # noqa: E402
import logging  # noqa: E402
from requests.utils import getproxies  # noqa: E402
logging.basicConfig(level=logging.INFO)
from requests import Session  # noqa: E402

def mask_log(log_msg):
    if( (log_msg is None) or (len(log_msg) == 0 )):
        return log_msg
    for i in log_msg:
        tmp_prox = log_msg[i]
        parsed = urlparse(tmp_prox)
        if parsed.password is None:
            continue
        log_msg[i] = '{}://{}:{}@{}:{}'.format(parsed.scheme, '*****', '*****', parsed.hostname, parsed.port)
    return log_msg

def empty(value):
    if (value is None) or value == '' or not isinstance(value,str):
        return True
    return False

def build_proxy_url(proxy_protocol='http', proxy_address=None, proxy_port=None, proxy_username=None, proxy_password=None ):
    if empty(proxy_address) or empty(proxy_port):
        logging.warning('No user defined proxy will be tested')
        return None
    elif empty(proxy_username) or empty(proxy_password):
        logging.warning('Wont use proxy username or proxy password as they are not set.')
        return  '{}://{}:{}'.format(proxy_protocol,proxy_address, proxy_port)
    else:
        return '{}://{}:{}@{}:{}'.format(proxy_protocol, proxy_username, proxy_password, proxy_address, proxy_port)


def check_proxies(sc_address, sc_verify_ssl, proxy_protocol, proxy_address, proxy_port, proxy_username, proxy_password, *args, **kwargs):
    proxies = {
        'No Proxy': {},
        'Environment Proxy': getproxies(),
    }
    purl =  build_proxy_url(proxy_protocol, proxy_address, proxy_port, proxy_username, proxy_password)
    if purl:
        proxies['User Proxy'] = {'http': purl, 'https': purl}

    for msg in proxies:
        proxy = proxies[msg]
        s = Session()
        s.trust_env = False
        clean_proxy = mask_log(deepcopy(proxy))
        logging.info('Testing - {} - With proxy: {}'.format(msg, clean_proxy))
        try:
            tsc = TenableSC(host=sc_address, proxies=proxy, ssl_verify=sc_verify_ssl, timeout=10, session=s, retries=1)  # noqa: F841
            logging.info('{} - Worked!'.format(msg))
        except Exception as err:
            print(err)
            logging.error('{} - didnt work!'.format(msg))
            logging.error('{}'.format(err))
            pass

if __name__ == '__main__':
    ### T.sc Required ###
    sc_address = 'sc.example.com'   # FQDN/IP address of t.sc instance
    ### T.sc Optional ###
    sc_verify_ssl = False  # True/False verify the certificate on T.sc instance False for self signed cert
    ### Proxy Required ###
    proxy_protocol = 'http'  # http/https
    proxy_address = '' # FQDN/IP address of proxy
    proxy_port = '3128' # proxy port
    ### Proxy Optional ###
    proxy_username = ''
    proxy_password = ''

    ## DO NOT EDIT BELOW ##
    check_proxies(
        sc_address,
        sc_verify_ssl,
        proxy_protocol,
        proxy_address,
        proxy_port,
        proxy_username,
        proxy_password
    )
