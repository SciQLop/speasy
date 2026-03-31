class HapiError(Exception):
    pass


class HapiRequestError(HapiError):
    """4xx — Client Error (unkown dataset, bad date format, ...) """
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class HapiServerError(HapiError):
    """5xx — Server Error """
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class HapiNoData(HapiError):
    """1201 — Valid request, but no available data on time range"""
    pass
