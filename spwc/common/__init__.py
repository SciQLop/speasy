

def listify(obj:list or object)->list:
    if type(obj) is list:
        return obj
    else:
        return [obj]
