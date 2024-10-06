# Trixel Lookup Service

The *Trixel Lookup Service (TLS)* is responsible for managing initial communication with contributing measurement stations and directing them towards the *Trixel Management Server (TMS)* responsible for them.
This services will manage multiple TMSs and spread Trixel IDs across them to efficiently manage network traffic and too keep communication local.
Furthermore, this service will also provide references to Trixel History Servers.

For the time being, due to time restrictions and since this a prototype in its very early stages, only a single TMS will be supported.

## Development

This project is built on FAST-API and Sqlalchemy. For local development of the TLS, the use of an SQLite database is sufficient.
Environment variables can be used to configure how the database is accessed, see [here](src/database.py) for more details.
Setting `TLS_ALLOW_INSECURE_TMS` to `false` is advised when the TMS deployment does not support `https` (reverse-proxy-less local deployment).
Use `fastapi dev src/trixellookupserver.py --port <port-nr>` during development.
The client module can be generated with the help of the [generate_client.py](client_generator/generate_client.py) which is also used during continuous deployment.

[Pre-commit](https://pre-commit.com/) is used to enforce code-formatting, formatting tools are mentioned [here](.pre-commit-config.yaml).
[pytest](https://pytest.org/) is used for testing.

## Deployment

The continuous deployment pipeline generates [docker images](https://hub.docker.com/r/tillfleisch/trixellookupserver/tags) which can be used for deployment of the TLS.
Use `docker run` or a compose-file like this to run the TLS.

```yaml
services:
  trixellookupserver:
    image: tillfleisch/trixellookupserver:latest
    ports:
      - 4665:80
    environment:
      - TLS_LOG_LEVEL=5
    restart: always
```
