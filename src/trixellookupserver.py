"""Entry point for the Trixel Lookup Service API."""

import packaging.version
import pkg_resources
import uvicorn
from fastapi import FastAPI

from schema import Ping, Version

api_version = pkg_resources.get_distribution("trixellookupserver").version

app = FastAPI(
    title="Trixel Lookup Service",
    summary="""Manages Trixel Managements Servers (TMS) and their Trixel ID responsibilities.
               Coordinates initial communication to determine the correct TMS for a contributor.""",
    version=api_version,
    root_path=f"/v{packaging.version.Version(api_version).major}",
)


@app.get(
    "/ping",
    name="Ping",
    summary="ping ... pong",
)
def ping() -> Ping:
    """Return a basic ping message."""
    return Ping()


@app.get(
    "/version",
    name="Version",
    summary="Get the precise current semantic version.",
)
def get_semantic_version() -> Version:
    """Get the precise version of the currently running API."""
    return Version(version=api_version)


def main() -> None:
    """Entry point for cli module invocations."""
    uvicorn.main("trixellookupserver:app")


if __name__ == "__main__":
    main()
