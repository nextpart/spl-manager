# -*- coding: utf-8 -*-

# %%
from pathlib import Path

from rich import print

from spl.__main__ import SplManager

# pd.set_option("display.max_rows", 100)

# %%
spl = SplManager(interactive=False)
cloud = spl.manager(conn="nxtp-cloud")
onprem = spl.manager(conn="nxtp-onprem")

# %%
local_apps = spl.apps(
    path=Path("../../../../nextpart_splunking/apps").resolve().absolute(), name="*"
)
local_apps_names = [path.name for path in local_apps._paths]
local_apps_names

# %%
cloud_apps = cloud.client.apps.list()
cloud_apps_names = [app.name for app in cloud_apps]
cloud_apps_names


# %%
onprem_apps = onprem.client.apps.list()
onprem_apps_names = [app.name for app in onprem_apps]
onprem_apps_names

# %% DIFFERENCE BETWEEN STAGES
def diff(one=onprem_apps_names, two=cloud_apps_names):
    return [app for app in one if app not in two and "Agent" not in app]


# %%
print(diff(one=local_apps_names, two=cloud_apps_names))

# %%
