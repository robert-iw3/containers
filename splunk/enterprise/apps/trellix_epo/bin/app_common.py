import base64
import configparser
import os
import hashlib
import datetime
import requests
from time import sleep
from dateutil import tz

"""
Definition of base variables used in the program
"""
FROM_TZ = tz.gettz('UTC')
TO_TZ = tz.tzlocal()
helper = None
AUTH_URL = "https://iam.cloud.trellix.com/iam/v1.1/token"
EVENT_PATH = '/eventservice/api/v2/events'
HEADERS = {
    'Accept': 'application/json',
}

#Definition of classes "RetryException" and "UnRetryException", used to manage exceptions in requests
class RetryException(Exception):
    pass

class UnRetryException(Exception):
    pass

#Function "set_helper" used to set the global helper from Splunk
def set_helper(hlp):
    global helper
    helper = hlp

#Function "format_iso_time" used to set timestamp in ISO format required from MVision API
def format_iso_time(ft_rule='%Y-%m-%dT%H:%M:%S.%f', delta_sec=0):
    calc_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=delta_sec)
    calc_time = calc_time.strftime(ft_rule)[:-3]+"Z"
    return calc_time

#Function "format_timestamp" used to convert timestamp in POSIX/Epoch format to human readable format
def format_timestamp(timestamp, ft_rule='%Y-%m-%d %H:%M:%S'):
    if len(str(timestamp))>10:
        timestamp=timestamp/1000
    calc_time = datetime.datetime.fromtimestamp(timestamp).strftime(ft_rule)
    return calc_time

#Function "format_time" used to convert timestamp string from ISO format to common format used in timezone
def format_time(timestamp):
    if len(timestamp)>21:
        ft_rule='%Y-%m-%dT%H:%M:%S.%fZ'
    else:
        ft_rule='%Y-%m-%dT%H:%M:%SZ'
    input_time = datetime.datetime.strptime(timestamp,ft_rule)
    input_time = input_time.replace(tzinfo=FROM_TZ)
    calc_time = input_time.astimezone(TO_TZ)
    calc_time = datetime.datetime.strftime(calc_time,'%Y-%m-%d %H:%M:%S')
    return calc_time

#Function "gen_context_path" used to generate context path where last execution/detection time were saved
def gen_context_path(input_name):
    encode_str = base64.b64encode(bytes(input_name, 'utf-8'))
    suffix = hashlib.sha1(encode_str).hexdigest()
    return (os.path.join(os.environ["SPLUNK_HOME"],'etc','apps','Trellix_Splunk','data'), f'status-{suffix}.ini')

#Function "fetch_context" used to create context path and file where last execution/detection time were saved or get time from it. *** IS NOT USED TO UPDATE, use "update_context" instead.
def read_config(input_name,stanza,since_val):
    ck_path, file_name = gen_context_path(input_name)
    status_file = os.path.join(ck_path, file_name)
    config = configparser.ConfigParser()
    if not os.path.exists(ck_path):
        os.makedirs(ck_path,0o755)
    if not os.path.exists(status_file):
        config[stanza]= {'since': since_val}
        with open(status_file, 'w') as config_file:
            config.write(config_file)
    else:
        config.read(status_file)
        if not config.has_section(stanza):
            config[stanza] = {'since': since_val}
            with open(status_file,'w') as config_file:
                config.write(config_file)
        else:
            return config[stanza]['since']
    return since_val

#Function "update_context" used to update context file where last execution/detection time were saved.
def update_config(input_name,stanza,since_val):
    ck_path, file_name = gen_context_path(input_name)
    status_file = os.path.join(ck_path, file_name)
    config = configparser.ConfigParser()
    if not os.path.exists(ck_path):
        os.makedirs(ck_path,0o755)
    if not os.path.exists(status_file):
        config.set(stanza,'since',since_val)
        with open(status_file, 'w') as config_file:
            config.write(config_file)
    else:
        config.read(status_file)
        config.set(stanza,'since',since_val)
        with open(status_file, 'w') as config_file:
            config.write(config_file)
    return True

#Function "raise_for_status" used to get status from response object from request. Let's know in a human readable format what happen if status code is different to 200 - OK
def raise_for_status(response):
    if isinstance(response.reason, bytes):
        try:
            reason = response.reason.decode('utf-8')
        except UnicodeDecodeError:
            reason = response.reason.decode('iso-8859-1')
    else:
        reason = response.reason

    if 400 <= response.status_code < 500:
        http_error_msg = u'%s Client Error: %s for url: %s' % (
            response.status_code, reason, response.url)
        raise UnRetryException(http_error_msg)

    elif 500 <= response.status_code < 600:
        http_error_msg = u'%s Server Error: %s for url: %s' % (
            response.status_code, reason, response.url)
        raise RetryException(http_error_msg)

#Function "request_help" creates a helper for HTTP/s requests, allowing to manage retries and delay for retries.
def request_help(max_retries,backoff_sec):
    #Sub-function "send_request" manages requests main method to use multiples HTTP/s methods (GET, POST, PUT, UPDATE, etc), instead use "requests.get" or "requests.post" functions
    def send_request(url,method,parameters=None,payload=None,headers=None, proxies=None, timeout=55):
        attempt_times, attempt_delay = max_retries, backoff_sec
        response = None
        while attempt_times >= 0:
            try:
                if "https" in url:
                    response = requests.request(method, url, params=parameters, headers=headers, data=payload, proxies=proxies, timeout=timeout)
                    raise_for_status(response)
                    return response
                else:
                    return "Error: URL protocol must be HTTPS"
            except RetryException as e:
                pass
            except UnRetryException as e:
                break
            attempt_times -= 1
            if attempt_times != 0:
                sleep(attempt_delay)
        return response
    return send_request

def get_token(username, password, tenant, proxies):
    try:
        payload = {
            'username':username,
            'password': password,
            'client_id': '0oae8q9q2y0IZOYUm0h7',
            'scope': 'epo.evt.r dp.im.r',
            'grant_type':'password',
        }
        if tenant != "default":
            payload['tenant_id'] = tenant
        reqhelp = request_help(2,10)
        res = reqhelp(url=AUTH_URL,method="POST",proxies=proxies,payload=payload,headers=HEADERS)
        res.raise_for_status()
        access_token = res.json()['access_token']
        return access_token
    except requests.exceptions.Timeout as e:
        helper.log_error("[MVision EPO] Request timeout error: %s" % str(e))
        return 1
    except requests.exceptions.HTTPError as e:
        helper.log_error("[MVision EPO] Request error: %s %s" % (str(e), str(AUTH_URL)))
        return 1
    except Exception as e:
        helper.log_error("[MVision EPO] Request exception: %s" % str(e))
        return 1

def mapSeverity(severity):
    if not isinstance(severity,int):
        return severity
    severity_map = {
        2: 'High',
        3: 'Medium',
        5: 'Low',
    }
    if severity in severity_map:
        return severity_map[severity]
    else:
        return 'Informational'

def keyMap(key):
    key_map = {
        'analyzerdatversion': 'signature_version',
        'targetprocessname': 'process_name',
        'targetfilename': 'file_name',
        'targethash': 'file_hash',
        'targetipv4': 'src_ip',
        'targetmac': 'mac',
        'targetusername': 'src_user',
        'targetport': 'src_port',
        'targethostname': 'hostname',
        'threatactiontaken': 'action',
        'analyzerversion': 'product_version',
        'analyzername': 'vendor_product',
        'sourceprocesshash': 'process_hash',
    }
    if key in key_map:
        return key_map[key]
    else:
        return key