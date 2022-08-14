import pyistp
from ...products import SpeasyVariable


def load_variable(variable="", file=None, buffer=None) -> SpeasyVariable or None:
    istp = pyistp.load(file=file, buffer=buffer)
    if istp:
        if variable in istp.data_variables():
            var = istp.data_variable(variable)
        elif variable.replace('-', '_') in istp.data_variables():  # THX CSA/ISTP
            var = istp.data_variable(variable.replace('-', '_'))
        else:
            return None
        if var:
            if len(var.axes) <= 2:
                if len(var.axes) == 2:
                    y = var.axes[1].values.copy()
                else:
                    y = None
                return SpeasyVariable(time=var.axes[0].values.copy(), data=var.values.copy(), meta=var.attributes, y=y,
                                      columns=var.labels)
    return None
