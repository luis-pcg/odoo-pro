"""Mint the API key the master will use against this client."""

import json

args = json.load(open("/tmp/sync_manual_args.json"))
admin = env.ref("base.user_admin")  # noqa: F821
key = env["res.users.apikeys"].with_user(admin).sudo()._generate(  # noqa: F821
    None, args.get("name", "Sincronización de nómina"), False
)
env.cr.commit()  # noqa: F821
print("KEY=%s" % key)
