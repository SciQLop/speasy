class TimetableIndex:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __repr__(self):
        return f'<TimetableIndex: {self.name}, id: {self.uid}>'


class DatasetIndex:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __repr__(self):
        return f'<DatasetIndex: {self.name}, id: {self.uid}>'


def xmlid(index_or_str):
    if type(index_or_str) is str:
        return index_or_str
    if hasattr(index_or_str,'uid'):
        return index_or_str.uid
    else:
        raise TypeError("given parameter is not a compatible index")
