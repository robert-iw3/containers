"""
Microsoft Entra ID sign-in logs, JSON as the Graph API emits them.

The cloud identity plane. Individually large records, low rate, and almost
entirely control evidence - which is why it is a good counterexample: not every
feed should be reduced.
"""

import json
import random
import environment

KEY = "entra_signin"
SOURCETYPE = "azure:aad:signin"
SOURCE = "graph:signIns"
SHARE = 0.1

# The indexed field the lab matches this source's control evidence on.
# None means the control is evidenced by the source arriving at all.
CONTROL_FIELD = None

CONTROLS = [
    ("IA-2",    "CSF PR.AA-02", ["signIn"], True, "identification and authentication to cloud services"),
    ("IA-2(1)", "CSF PR.AA-03", ["mfaDetail"], True, "multifactor authentication"),
    ("AC-7",    "CSF DE.CM-01", ["failed signIn"], True, "unsuccessful logon attempts"),
    ("AC-17",   "CSF PR.AA-05", ["signIn from untrusted location"], True, "remote access"),
    ("AU-12",   "CSF DE.CM-01", ["signIn"], True, "audit generation"),
]
DROPPED_BY_DESIGN = []


def emit(rng, host, record_id, ts):
    user = rng.choice(environment.USERS)
    ok = rng.random() > 0.07
    rec = {
        "id": f"{record_id:08x}-0000-0000-0000-000000000000",
        "createdDateTime": ts,
        "userPrincipalName": f"{user}@{environment.DOMAIN}",
        "userDisplayName": user.replace(".", " ").title(),
        "appDisplayName": rng.choice(["Office 365 Exchange Online", "Microsoft Teams",
                                      "Azure Portal", "SharePoint Online"]),
        "ipAddress": rng.choice(environment.EXTERNAL_HOSTS),
        "clientAppUsed": rng.choice(["Browser", "Mobile Apps and Desktop clients"]),
        "conditionalAccessStatus": "success" if ok else "failure",
        "isInteractive": True,
        "riskLevelDuringSignIn": rng.choice(["none", "none", "none", "low", "medium"]),
        "riskState": "none",
        "status": {"errorCode": 0 if ok else 50126,
                   "failureReason": "Other." if ok else "Invalid username or password.",
                   "additionalDetails": "MFA requirement satisfied by claim in the token" if ok else ""},
        "deviceDetail": {"deviceId": f"{record_id:08x}", "displayName": rng.choice(environment.WORKSTATIONS),
                         "operatingSystem": "Windows 10", "browser": "Edge 140.0",
                         "isCompliant": True, "trustType": "Azure AD joined"},
        "location": {"city": "Reading", "state": "England", "countryOrRegion": "GB",
                     "geoCoordinates": {"latitude": 51.45, "longitude": -0.97}},
        "mfaDetail": {"authMethod": "PhoneAppNotification", "authDetail": "User approved"} if ok else {},
        "authenticationRequirement": "multiFactorAuthentication",
    }
    return json.dumps(rec), {"success": ok, "user": user}
