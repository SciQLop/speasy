class SpeasyProduct(object):
    __slots__ = ['__request_params']

    def __init__(self, request_params=None):
        self.__request_params = request_params

    @property
    def request_params(self):
        return self.__request_params
