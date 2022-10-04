import os.path
import logging
from typing import List
import pyistp
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex, SpeasyIndex

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


def filter_meta(attributes):
    keep_list = ['CATDESC', 'FIELDNAM', 'UNITS', 'UNIT_PTR', 'DISPLAY_TYPE', 'LABLAXIS', 'LABL_PTR_1', 'LABL_PTR_2',
                 'LABL_PTR_3']
    return {key: value for key, value in attributes.items() if key in keep_list}


def load_master_cdf(path, dataset: DatasetIndex):
    skip_count = 0
    try:
        cdf = pyistp.load(path)
        for name in cdf.data_variables():
            try:
                datavar = cdf.data_variable(name)
                if datavar is not None:
                    index = ParameterIndex(name=name, provider="cda", uid=f"{dataset.serviceprovider_ID}/{name}",
                                           meta=filter_meta(datavar.attributes))
                    index.start_date = dataset.start_date
                    index.stop_date = dataset.stop_date
                    index.dataset = dataset.spz_uid()
                    dataset.__dict__[name] = index
            except IndexError or RuntimeError:
                print(f"Issue loading {name} from {path}")
                skip_count += 1
    except RuntimeError:
        print(f"Issue loading {name} from {path}")
        skip_count += 1
    return skip_count


def _extract_datasets(root: SpeasyIndex):
    def extract_datasets(node: SpeasyIndex, datasets: List):
        if isinstance(node, DatasetIndex):
            datasets.append(node)
        elif isinstance(node, SpeasyIndex):
            for child in node.__dict__.values():
                extract_datasets(child, datasets)

    datasets = []
    extract_datasets(root, datasets)
    return datasets


def update_tree(root: SpeasyIndex, master_cdf_dir):
    skip_count = 0
    datasets = _extract_datasets(root)
    for dataset in datasets:
        master_cdf_fname = dataset.mastercdf.split('/')[-1]
        full_path = os.path.join(master_cdf_dir, master_cdf_fname)
        if os.path.exists(full_path):
            skip_count += load_master_cdf(full_path, dataset)
        else:
            skip_count += 1
    print(f"{skip_count} datasets or variables skipped")
