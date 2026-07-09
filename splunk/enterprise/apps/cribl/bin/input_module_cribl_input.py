# encoding = utf-8

import os
import sys
import time
import datetime
import json
import calendar

'''
    IMPORTANT
    Edit only the validate_input and collect_events functions.
    Do not edit any other part in this file.
    This file is generated only once when creating the modular input.
'''
'''
# For advanced users, if you want to create single instance mod input, uncomment this method.
def use_single_instance_mode():
    return True
'''

def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    # This example accesses the modular input variable
    # username = definition.parameters.get('username', None)
    # password = definition.parameters.get('password', None)
    # cribl_url = definition.parameters.get('cribl_url', None)
    # log_id = definition.parameters.get('log_id', None)
    # earliest = definition.parameters.get('earliest', None)
    pass

def collect_events(helper, ew):

    opt_cribl_url = helper.get_arg('cribl_url')
    opt_log_id = helper.get_arg('log_id')
    stanza_name = helper.get_input_stanza_names()

    if opt_cribl_url.startswith("https://"):

        opt_authentication_token = get_api_token(helper,opt_cribl_url)

        r_json = api_call(helper,opt_authentication_token,opt_cribl_url,opt_log_id,stanza_name)

        event_check_pointed=checkpoint(helper,r_json,opt_log_id,stanza_name)

        if len(event_check_pointed)==0:
            helper.log_info("No events indexed")
        else:
            data =json.dumps(event_check_pointed)

            event=helper.new_event(data, time=None, host=opt_cribl_url, index=None, source=helper.get_input_stanza_names(), sourcetype=opt_log_id.split('.')[0], done=True, unbroken=True)
            ew.write_event(event)
            helper.log_info("indexed new events")
    else:
        helper.log_error("cribl_url must use https protocol")

def api_call(helper,opt_authentication_token,opt_cribl_url,opt_log_id,stanza_name):



    opt_earliest = helper.get_arg('earliest')
    state = helper.get_check_point(f"lt:{stanza_name}:{opt_log_id}")

    header={
        'accept': 'application/json',
        'Authorization': 'Bearer {}'.format(opt_authentication_token)
        }
    if state ==None:
        if opt_earliest == None:
            opt_earliest = time.time()-(86400*30)
    else:
        opt_earliest = convertTimeState(state)

    parameter={
        'et':'{}'.format(opt_earliest)
        }

    url='{}/api/v1/system/logs/{}'.format(opt_cribl_url,opt_log_id)

    response = helper.send_http_request(url, 'GET', parameters=parameter, payload=None,
                                        headers=header, cookies=None, verify=False, cert=None,
                                        timeout=None, use_proxy=True)

    r_status = response.status_code
    if r_status != 200:
        helper.log_info("error {}".format(r_status))
        response.raise_for_status()

    return response.json()

def get_api_token(helper,opt_cribl_url):

    opt_global_account = helper.get_arg('global_account')

    header={
        'accept': 'application/json',
        'Content-Type': 'application/json'
        }

    data=opt_global_account

    url = '{}/api/v1/auth/login'.format(opt_cribl_url)


    response_token = helper.send_http_request(url, 'POST', parameters=None, payload=data,
                                        headers=header, cookies=None, verify=False, cert=None,
                                        timeout=None, use_proxy=False)
    r_status = response_token.status_code
    if r_status != 200:
        helper.log_info("error {}".format(r_status))
        response_token.raise_for_status()

    rt_json = response_token.json()
    rt_token = rt_json["token"]

    return rt_token

#convert the time state to epoch time
def convertTimeState(state):
    timeState = calendar.timegm(time.strptime(state, '%Y-%m-%dT%H:%M:%S.%fZ'))
    return timeState

def checkpoint(helper,r_json,opt_log_id,stanza_name):

    results=[]

    itemsEvents = r_json["items"][0]["events"]

    if len(itemsEvents)>0:

        temp = " "
        stanza_name = helper.get_input_stanza_names()

        for event in itemsEvents:

            temp= event["time"]

            key = f"{stanza_name}:{opt_log_id}:{temp}"

            state = helper.get_check_point(key)

            if state is None:
                results.append(event)
                helper.save_check_point(key,"Indexed")
            #helper.delete_check_point(key)
        helper.save_check_point(f"lt:{stanza_name}:{opt_log_id}",temp)
        #helper.delete_check_point(f"lt:{stanza_name}:{opt_log_id}")

    return results
