# Trixel Lookup Service

The *Trixel Lookup Service (TLS)* is responsible for managing initial communication with contributing measurement stations and directing them towards the *Trixel Management Server (TMS)* responsible for them.
This services will manage multiple TMSs and spread Trixel IDs across them to efficiently manage network traffic and too keep communication local.
Furthermore, this service will also provide references to Trixel History Servers.

For the time being, due to time restrictions and since this a prototype in its very early stages, only a single TMS will be supported.
