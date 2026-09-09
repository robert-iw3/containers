"""
Source modules for the environment data set.

Each module declares KEY, SOURCETYPE, SOURCE, SHARE (percent of environment BYTES),
CONTROLS, DROPPED_BY_DESIGN and emit(rng, host, record_id, ts) -> (raw, meta).
Adding a feed means adding a module here and nothing else.

SHARE values are engineering estimates for a ~10,000-endpoint enterprise, not
measurements, and they sum to 100. They set the data set mix, so they are the
single most consequential assumption in the whole measurement: the reduction a
pipeline achieves is mostly a property of what the environment sends it.
"""

from . import (asa_vpn, cisco_ise, entra_signin, kube_stdout, linux_audit,
               netflow, pan_firewall, proxy, suricata, sysmon, web_access,
               win_dhcp, win_dns, win_security, win_system)

ALL = [pan_firewall, win_security, win_dns, netflow, kube_stdout, suricata,
       web_access, proxy, sysmon, cisco_ise, win_system, asa_vpn,
       linux_audit, win_dhcp, entra_signin]
