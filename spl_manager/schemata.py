"""SPL management schemas."""
# %%
CONNECTION_CONFIG_SCHEMA = {
    "CONNECTIONS": {
        "type": "dict",
        "valuesrules": {
            "type": "dict",
            "schema": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "username": {"type": "string", "required": False},
                "password": {"type": "string", "required": False},
                "token": {"type": "string", "required": False},
            },
        },
    },
}
SAMPLES_CONFIG_SCHEMA = {
    "SAMPLES": {
        "type": "dict",
        "valuesrules": {
            "type": "dict",
            "schema": {
                "query": {"type": "string"},
                "earliest": {"type": "string"},
                "latest": {"type": "string"},
            },
        },
    },
}

SPLUNKBASE_CONFIG_SCHEMA = {
    "SPLUNKBASE": {
        "type": "dict",
        "schema": {
            "username": {"type": "string"},
            "password": {"type": "string"},
            "apps": {
                "type": "dict",
                "valuesrules": {
                    "type": "dict",
                    "schema": {
                        "id": {"type": "string"},
                        "version": {"type": "string"},
                    },
                },
            },
        },
    }
}
DOCKER_CONFIG_SCHEMA = {
    "DOCKER": {
        "type": "dict",
        "schema": {
            "socket": {"type": "string"},
            "image": {"type": "string"},
            "environment": {"type": "dict"},
        },
    }
}

AZURE_DEVOPS_CONFIG_SCHEMA = {
    "azure_devops": {
        "type": "dict",
        "schema": {
            "organization": {"type": "string"},
            "project": {"type": "string"},
            "feed": {"type": "string"},
            "pat": {"type": "string"},
        },
    }
}

CONFIG_SCHEMA = {
    key: val
    for schema in [
        CONNECTION_CONFIG_SCHEMA,
        SAMPLES_CONFIG_SCHEMA,
        SPLUNKBASE_CONFIG_SCHEMA,
        DOCKER_CONFIG_SCHEMA,
    ]
    for key, val in schema.items()
}
