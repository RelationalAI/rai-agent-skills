## Programmatic Configuration

```python
from relationalai.config import create_config
```

### Auto-discovery (no args)

```python
cfg = create_config()  # finds raiconfig.yaml walking up from CWD
```

### Programmatic with dicts

```python
import os
cfg = create_config(
    connections={
        "sf": {
            "type": "snowflake",
            "authenticator": "username_password",
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
        }
    },
    default_connection="sf",
    reasoners={"logic": {"size": "HIGHMEM_X64_S"}},
)
```

### Typed connection objects

```python
from relationalai.config import create_config, UsernamePasswordAuth

cfg = create_config(
    connections={
        "sf": UsernamePasswordAuth(
            account="my_account",
            warehouse="my_warehouse",
            user="my_user",
            password="my_password",
        )
    }
)
```

### Getting sessions from config

```python
session = cfg.get_session()                                # default connection
session = cfg.get_session(SnowflakeConnection)             # typed, default
conn = cfg.get_connection(SnowflakeConnection, name="sf")  # by name

# Or from the model (session is lazy — triggers on first job):
from relationalai.semantics import Model
model = Model("MyModel")
session = model.config.get_session()
session.sql("SELECT 1").collect()  # verify connection works

# Force a fresh session (e.g., after rotating credentials):
conn = model.config.get_default_connection()
conn.clear_session_cache()
```

### Basic model creation

```python
from relationalai.semantics import Model

model = Model("my_model")              # auto-discovers raiconfig.yaml
model = Model("my_model", config=cfg)  # explicit config
```
