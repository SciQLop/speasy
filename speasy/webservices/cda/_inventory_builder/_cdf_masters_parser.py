import os.path
import logging
import pyistp
from speasy.inventories import flat_inventories
from speasy.core.inventory.indexes import ParameterIndex

log = logging.getLogger(__name__)


def extract_variable(variable):
    return {
        'shape': variable.shape[1:],
        'attributes': {name: str(value) for name, value in variable.attrs.items()}
    }


def extract_variables(cdf):
    return {
        name: extract_variable(v) for name, v in cdf.items()
    }


def load_master_cdf(path, dataset):
    skip_count = 0
    try:
        cdf = pyistp.load(path)
        for name in cdf.data_variables():
            try:
                datavar = cdf.data_variable(name)
                if datavar is not None:
                    index = ParameterIndex(name=name, provider="cda", uid=f"{dataset.serviceprovider_ID}/{name}",
                                           meta=datavar.attributes)
                    dataset.__dict__[name] = index
            except IndexError or RuntimeError:
                print(f"Issue loading {name} from {path}")
                skip_count += 1
    except RuntimeError:
        print(f"Issue loading {name} from {path}")
        skip_count += 1
    return skip_count


def update_tree(master_cdf_dir):
    skip_count = 0
    for dataset in flat_inventories.cda.datasets.values():
        master_cdf_fname = dataset.mastercdf.split('/')[-1]
        full_path = os.path.join(master_cdf_dir, master_cdf_fname)
        if os.path.exists(full_path):
            skip_count += load_master_cdf(full_path, dataset)
        else:
            skip_count += 1
    print(f"{skip_count} datasets or variables skipped")
