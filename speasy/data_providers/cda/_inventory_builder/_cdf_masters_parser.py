import logging
import os.path
from typing import List
import pyistp

from speasy.core.cdf.inventory_extractor import extract_parameters, filter_dataset_meta
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex, SpeasyIndex
from speasy.core import fix_name

log = logging.getLogger(__name__)


def _patch_parameter(parameter: ParameterIndex, dataset: DatasetIndex):
    parameter.start_date = dataset.start_date
    parameter.stop_date = dataset.stop_date
    parameter.dataset = dataset.spz_uid()
    return parameter


def load_master_cdf(path, dataset: DatasetIndex):
    cdf = pyistp.loader.ISTPLoader(path)
    dataset.__dict__.update(
        {fix_name(p.spz_name()): p for p in
         map(lambda p: _patch_parameter(p, dataset), extract_parameters(cdf, provider="cda",
                                                                        uid_fmt=f"{dataset.serviceprovider_ID}/{{var_name}}"))})
    dataset.__dict__.update(filter_dataset_meta(cdf))



def _extract_datasets(root: SpeasyIndex) -> List[DatasetIndex]:
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
    datasets = _extract_datasets(root)
    for dataset in datasets:
        master_cdf_fname = dataset.mastercdf.split('/')[-1]
        full_path = os.path.join(master_cdf_dir, master_cdf_fname)
        if os.path.exists(full_path):
            load_master_cdf(full_path, dataset)
