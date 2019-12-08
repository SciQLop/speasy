from datetime import datetime, timezone
from dateutil.parser import parse
import os

def listify(obj: list or object) -> list:
    if type(obj) is list:
        return obj
    else:
        return [obj]


def make_utc_datetime(input_dt: str or datetime) -> datetime:
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    return input_dt.replace(tzinfo=timezone.utc)


def mkdir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
