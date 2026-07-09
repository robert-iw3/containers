# encoding = utf-8

from app_common import *
import json
import requests
from urllib.parse import unquote, urlparse



def validate_input(helper, definition):
    global_account = definition.parameters.get('global_account', None)
    if global_account is None:
        raise ValueError('An account is required. Please check your add-on configuration')
    interval = definition.parameters.get('interval',None)
    if interval is not None and int(interval) < 10:
        raise ValueError('The minimum public API access interval cannot be less than 10 seconds')

def collect_events(helper, ew):
    STANZA = helper.get_input_stanza_names()
    username = helper.get_arg('global_account')['username']
    password = helper.get_arg('global_account')['password']
    endpoint = helper.get_arg('global_account')['url']
    https_proxy = helper.get_global_setting("https_proxy")
    tenant_id = helper.get_arg('global_account')['tenant_id']
    backoff_time = float(helper.get_global_setting("backoff_time") or 10)

    proxies = {}

    if https_proxy is not None:
        proxies['https'] = https_proxy

    if not endpoint:
        helper.log_error("[MVision EPO] No valid config, will pass")
        return 0

    access_token = get_token(
        username=username,
        password=password,
        tenant=tenant_id,
        proxies=proxies
    )
    HEADERS['Authorization'] = 'Bearer '+access_token

    parse_url = urlparse(endpoint)
    if not "https" in  parse_url.scheme:
        return 0
    else:
        endpoint = "{}://{}".format(parse_url.scheme, parse_url.netloc)
        helper.log_info(f"[MVision EPO] Get endpoint: {endpoint}")



    nowTime = format_iso_time()

    type = ["threats","incidents"]
    for t in type:
        file_context = read_config(STANZA, t, str(format_iso_time(delta_sec=360000)))

        params = {
            'type': t,
            'since': file_context,
            'until': nowTime,
            'limit': 1000,
            'sort': 'asc',
        }

        req_help = request_help(2, backoff_time)

        nextFlag = True
        nextItem = None

        while nextFlag:
            if nextItem:
                params['since'] = nextItem

            try:
                res = req_help(
                    url=endpoint + EVENT_PATH,
                    method="GET",
                    parameters=params,
                    headers=HEADERS,
                    proxies = proxies
                )
                res.raise_for_status()
                data = res.json()
            except requests.exceptions.Timeout as e:
                helper.log_error("[MVision EPO] Request timeout error: %s" % str(e))
                return 1
            except requests.exceptions.HTTPError as e:
                helper.log_error("[MVision EPO] Request error: %s %s" % (str(e), str(endpoint)))
                return 1
            except Exception as e:
                helper.log_error("[MVision EPO] Request exception: %s" % str(e))
                return 1

            if res.ok:
                if len(data['Events']) == 0:
                    helper.log_info(f'[MVision EPO] No new MVision {t} identified')
                    nextFlag = False
                    update_config(STANZA, t, str(nowTime))
                else:
                    for raw_event in data['Events']:
                        event = {}
                        event['analyzertype'] = t
                        for key, value in raw_event.items():
                            key = keyMap(key)
                            event[key] = value['value']
                            if key == 'detectedutc':
                                event[key] = str(format_timestamp(value['value']))
                            if key == 'receivedutc':
                                event[key] = str(format_time(value['value']))
                            if key == 'eventtimelocal':
                                event[key] = str(format_timestamp(value['value']))
                            if key == 'threatseverity':
                                event[key] = mapSeverity(value['value'])
                        evt = helper.new_event(data=json.dumps(event), host='mvision:epo:api', index=helper.get_output_index(), source=helper.get_input_type(), sourcetype=helper.get_sourcetype(), done=True, unbroken=True)
                        ew.write_event(evt)
                    if 'Link' in res.headers and 'rel="next"' in res.headers['Link']:
                        nLinks = res.headers['Link'].split(";")
                        nextItem = unquote(nLinks[0]).split('after=')[1]
                        nextItem = json.loads(base64.b64decode(nextItem))['since']
                        nextFlag = True
                    else:
                        nextFlag = False
                        event_ldTime = format_time(data['Events'][-1]['receivedutc']['value'])
                        current_ldTime = format_time(nowTime)
                        if event_ldTime > current_ldTime:
                            helper.log_info(f'{event_ldTime} - {current_ldTime}')
                            nowTime = data['Events'][-1]['receivedutc']['value']
                        update_config(STANZA, t, str(nowTime))

            else:
                helper.log_error(f'[MVision EPO] Could not retrieve events: {res.status_code} - {res.reason}')
