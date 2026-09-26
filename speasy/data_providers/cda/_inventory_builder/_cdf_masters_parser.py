import logging
import multiprocessing
import os.path
import sys
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import List, Tuple
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


def _parse_master_cdf(path: str, uid_prefix: str) -> Tuple[List[ParameterIndex], dict]:
    cdf = pyistp.loader.ISTPLoader(path)
    parameters = extract_parameters(cdf, provider="cda", uid_fmt=f"{uid_prefix}/{{var_name}}", enable_cda_trick=True)
    return parameters, filter_dataset_meta(cdf)


def _attach_master(dataset: DatasetIndex, parsed: Tuple[List[ParameterIndex], dict]):
    parameters, dataset_meta = parsed
    dataset.__dict__.update({fix_name(p.spz_name()): _patch_parameter(p, dataset) for p in parameters})
    dataset.__dict__.update(dataset_meta)


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


def _masters_executor() -> Executor:
    # Parsing is pure-Python pyistp work, so threads would serialize on the GIL. Workers must be
    # forked: a spawned/forkserver worker re-imports speasy, whose import-time init_providers()
    # would start its own inventory build. The fork child only parses files, it never touches the
    # HTTP or cache locks that make forking a threaded process risky.
    # simplify: sequential on macOS/Windows where fork is unsafe/missing; only the proxy (Linux) cares.
    if sys.platform == "linux":
        return ProcessPoolExecutor(mp_context=multiprocessing.get_context("fork"))
    return ThreadPoolExecutor(max_workers=1)


def update_tree(root: SpeasyIndex, master_cdf_dir):
    datasets = [(dataset, os.path.join(master_cdf_dir, dataset.mastercdf.split('/')[-1]))
                for dataset in _extract_datasets(root)]
    datasets = [(dataset, path) for dataset, path in datasets if os.path.exists(path)]
    with _masters_executor() as executor:
        parsed = executor.map(_parse_master_cdf, [path for _, path in datasets],
                              [dataset.serviceprovider_ID for dataset, _ in datasets], chunksize=16)
        for (dataset, _), result in zip(datasets, parsed):
            _attach_master(dataset, result)
