# -*- coding: utf-8 -*-
# Sync props & transforms for certain apps

# Determine props & transforms from Syslog-Config TA on OnPrem
# Create missing stanzas in Splunk_TA_paloalto & TA-aruba_networks props
#
#


# %%
from rich import print

from spl.__main__ import SplManager

spl = SplManager(interactive=False)
# %%
instance = spl.manager(conn="nxtp-cloud")
# instance.namespace(context=True, app="-", sharing="app", owner="-")

# %%
instance.client.authority

# %%
[conf.name for conf in instance.client.confs.list()]

# %%
[(conf.name, conf.path) for conf in instance.client.confs.list()]

# %%
props = [conf for conf in instance.client.confs.list() if conf.name == "props"][0]
props

# %%
transforms = [conf for conf in instance.client.confs.list() if conf.name == "transforms"][0]
transforms

# %%
transforms.__dict__

# %%
transforms_stanzas = [stanza for stanza in transforms]
transforms_stanzas

# %%
[(stanza.name, stanza.access.app) for stanza in transforms_stanzas]

# %%
stanzas = [stanza for stanza in transforms]
stanzas

# %%
print(list({stanza.access.app for stanza in stanzas}))

# %%
print(list({stanza.access.app for stanza in transforms}))

# %%
apps = list(
    {stanza.access.app for stanza in stanzas}
)  # if stanza.access.app == "SPLUNK_SYSLOG_HELPER"]
apps


# %%
