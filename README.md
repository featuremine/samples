The Python runner has been retired. Open the standalone Titan desktop application
to configure and start sessions, save profiles, publish native
reference data, and view Carnitas messages and logs. See the root README.md.

The separate `tcp-strategy.py` remains a developer integration script for the
Carnitas service, rather than an application command-line mode. In Titan's
**Profile configuration**, use **Show tokens** beside **Order-entry token** to
obtain the profile's persistent order-entry token.
With Titan running, use a second terminal from the workspace root:

```sh
python3 titan/python/tcp-strategy.py --host localhost --port 8032 \
  --market-port 8033 --token '<TOKEN>' --schemas schemas/capnp
```

Use the host and ports shown in the profile's Connections section if they differ.
The script requires `pycapnp` and `msgpack`. It places simulated IOC buy orders using live prices
and waits for the fill-model responses. The order-entry token is saved with the
profile and copied into each session's configuration; it survives application
restarts. Saving an edited token applies it to future sessions, while existing
sessions retain their saved token. The script is not needed by the desktop
application.
