import os
import sys
import json
from ar_action_utility import get_ar_index, handle_error
from ar_action_connect import SCUtilNew

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def dowork(self):
    """Launches policy based remediation scan on Tenable SC server

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        dict: response from scan or error response
    """
    events = self.get_events()
    acc = self.get_param("account_name")
    for event in events:
        plugin_id = event.get("plugin_id")
        ip = event.get("ip")

        try:
            scu = SCUtilNew(self.session_key, acc, event=event)
        except Exception as e:
            return handle_error(
                self.logger,
                "SC",
                "Failed initializing TenableSC. Make sure you have SC account configured"
                " and you are running the AR action on SC notable event.",
                str(e)
            )

        # return and throw error if either of the plugin id/ip is not given or present in the event
        if not plugin_id or not ip:
            return handle_error(self.logger, "SC", "Either Plugin ID, or IP does not exist!")


        # create a policy based on ip, plugin id and its corresponding family id
        try:
            policy = scu.tsc.policies.create(
                name='Remediation Scan Policy of {} with Plugin {}'.format(ip, plugin_id),
                context='scan',
                template_id=1,
                preferences={
                    'portscan_range': 'default',
                    'tcp_scanner': 'no',
                    'syn_scanner': 'yes',
                    'udp_scanner': 'no',
                    'sync_firewall_detection': 'Automatic (normal)',
                },
                families=[
                    {
                        'id': scu.tsc.plugins.details(plugin_id)['family']['id'],
                        'plugins': [{'id': plugin_id}]
                    }
                ])
        except Exception as e:
            return handle_error(
                self.logger,
                "SC",
                "Failed to create policy with given plugin id: {} and ip: {}."
                .format(plugin_id, ip), str(e)
            )

        # start the policy based remediation scan on the target ip
        try:
            scan = scu.tsc.scans.create(
                'Remediation Scan Policy of {} with Plugin {}'.format(ip, plugin_id),
                1,
                host_tracking=True,
                policy_id=int(policy['id']),
                pluginID=plugin_id,
                targets=[ip],
                max_time=0,
                schedule={
                    'type': 'now'
                }
            )
            return scan
        except Exception as e:
            return handle_error(
                self.logger,
                "SC",
                "Failed to launch Remediation Scan Policy of {} with Plugin {}"
                .format(ip, plugin_id), str(e)
            )


def process_event(self, *args, **kwargs):
    """Write response event in sourcetype

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        int: return code
    """
    self.logger.info("Alert action launch_remediation_scan started.")
    content = dowork(self)
    self.addevent(json.dumps(content, ensure_ascii=False), sourcetype="tenable:sc:remedscan:ar")
    ar_index = get_ar_index(self.session_key)
    self.writeevents(index=ar_index)
    return 0
