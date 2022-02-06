# %%

from rich import print

from spl_manager.__main__ import SplManager

# %%
spl = SplManager(src="nxtp-onprem", dest="localhost", interactive=False)

# %%
print(
    "Properties: ",
    [prop for prop in dir(spl.sync.src.client) if not prop.startswith("_") and prop.endswith("s")],
)  # and prop.endswith("s")])
# %%
print(
    "Apps: ", [app.name for app in spl.sync.src.client.apps.list() if not app.name.startswith("_")]
)
print(
    {
        app.name: {"access": app.access, "content": app.content}
        for app in spl.sync.src.client.apps.list()
    }
)

# %%
print(
    "Indexes: ",
    [index.name for index in spl.sync.src.client.indexes.list() if not index.name.startswith("_")],
)
print("Index properties: ", spl.sync.src.client.indexes["aks_logs"].__dict__)
# %%
print(
    "Users: ",
    [user.name for user in spl.sync.src.client.users.list() if not user.name.startswith("_")],
)
print("User properties: ", spl.sync.src.client.users["analytics"].__dict__)

# %%
print(
    "Roles: ",
    [role.name for role in spl.sync.src.client.roles.list() if not role.name.startswith("_")],
)
print("Role properties: ", spl.sync.src.client.roles["developer"].__dict__)

# %%
roles = spl.sync.src.client.roles
roles["developer"].name


# %%
print(
    "Saved searches: ",
    [
        saved_search.name
        for saved_search in spl.sync.src.client.saved_searches.list()
        if not saved_search.name.startswith("_")
    ],
)
print("Saved search properties: ", spl.sync.src.client.saved_searches["User Add"].__dict__)

# %%
spl.sync.src.namespace(sharing="app", owner="admin", app="Splunk_TA_windows", context=False)

# %%
print(
    "Event types: ",
    [
        event_type.name
        for event_type in spl.sync.src.client.event_types.list()
        if not event_type.name.startswith("_")
    ],
)
print("Event type properties: ", spl.sync.src.client.event_types["linux_audit_anomalies"].__dict__)

# %%
print("Capabilities: ", spl.sync.src.client.capabilities)

# %%
spl.sync.dest.client.capabilities

# %%
spl.sync.src.client.users["analytics"].__dict__
