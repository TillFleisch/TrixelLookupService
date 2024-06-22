"""Logging helper which provides a logger with custom formatting and user-defined log-level."""

import logging
import os

import colorlog
from colorlog import ColoredFormatter

LOG_LEVEL = os.getenv("TLS_LOG_LEVEL", None)

__log_level = None
if LOG_LEVEL is not None:
    __log_level = LOG_LEVEL


formatter = ColoredFormatter(
    "%(asctime)s %(log_color)s%(levelname)s%(fg_white)s:%(name)s: %(log_color)s%(message)s",
    reset=True,
    style="%",
)


def get_logger(name: str | None):
    """
    Get a pre-configured logger.

    :param: name of the logger, if None the root logger is used
    :return: pre-configured logger
    """
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    if __log_level is not None:
        logger.setLevel(int(__log_level))
    return logger
