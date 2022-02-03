# -*- coding: utf-8 -*-
# %%

from rich import print

from spl_manager.__main__ import SplManager

# %%
cloud = SplManager(interactive=False).manager(conn="nxtp-cloud")
onprem = SplManager(interactive=False).manager(conn="nxtp-onprem")

# %%  DO THIS STEP FOR BOTH CLIENTS TO GET MORE DETAILS ON SAML/LDAP GROUPS
groups = []

for setting in onprem.client.confs["authentication"]:
    if "roleMap" in setting.path and "LDAP" in setting.path:
        print(setting.path)
        print(setting.__dict__["_state"]["content"])
        groups = []
        for key, val in setting.__dict__["_state"]["content"].items():
            if key not in ["disabled", "eai:appName", "eai:userName"]:
                groups += val.split(";")
        groups = list(set(groups))
        print(groups)
    elif "roleMap" in setting.path and "SAML" in setting.path:
        print(setting.path)
        print(setting.__dict__["_state"]["content"])
        for key, val in setting.__dict__["_state"]["content"].items():
            if key not in ["disabled", "eai:appName", "eai:userName"]:
                groups += val.split(";")
        groups = list(set(groups))
        print(groups)
    elif "SAML" in setting.path or "LDAP" in setting.path:
        print(setting.path)
        print(setting.__dict__["_state"]["content"])
