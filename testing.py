# -*- coding: utf-8 -*-
# %%
from rich import inspect, print
from spl.__main__ import SplManager
import splunklib.client as spl_client
# %%
spl = SplManager(src="nxtp-onprem", dest="localhost", interactive=False)

# %%
print("Properties: ",[prop for prop in dir(spl.sync.src.client) if not prop.startswith("_")]) # and prop.endswith("s")])
# %%
print("Apps: ",[app.name for app in spl.sync.src.client.apps.list() if not app.name.startswith("_")])
print(spl.sync.src.client.apps["Splunk_SOCToolkit"].content)
# %%
print("Indexes: ",[index.name for index in spl.sync.src.client.indexes.list() if not index.name.startswith("_")])
print("Index properties: ",spl.sync.src.client.indexes["aks_logs"].content)
# %%
print("Users: ",[user.name for user in spl.sync.src.client.users.list() if not user.name.startswith("_")])
print("User properties: ",spl.sync.src.client.users["analytics"].content)
# %%
print("Roles: ",[role.name for role in spl.sync.src.client.roles.list() if not role.name.startswith("_")])
print("Role properties: ",spl.sync.src.client.roles["developer"].content)
# %%
print("Saved searches: ",[saved_search.name for saved_search in spl.sync.src.client.saved_searches.list() if not saved_search.name.startswith("_")])
print("Saved search properties: ",spl.sync.src.client.saved_searches["User Add"].content)
# %%
print("Event types: ",[event_type.name for event_type in spl.sync.src.client.event_types.list() if not event_type.name.startswith("_")])
print("Event type properties: ",spl.sync.src.client.event_types["linux_audit_anomalies"].content)
# %%
print("Capabilities: ",spl.sync.src.client.capabilities)

# %%
spl.sync.dest.client.capabilities

# %%
spl.sync.src.client.users["analytics"].__dict__

# %%
spl.sync.src.client.roles["redbull"]

# %%
import splunk_appinspect

# %%
app = splunk_appinspect.App(location="../../../apps/FortiEDR_TA_nxtp", python_analyzer_enable=False)
app

# %%
# splunk_appinspect.main.validate(["../../../apps/FortiEDR_App_nxtp"])
# %%
inspect(app)

# %%
print(spl_client.Role.fields)


# %%
[prop for prop in dir(spl_client) if prop.endswith("s")]
