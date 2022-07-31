from ._xml_catalogs_parser import load_xml_catalog
from ._cdf_masters_parser import update_tree
from ....core.index import index
from ....config import cdaweb_inventory_data_path
import requests
from tempfile import NamedTemporaryFile
import tarfile
import os
from glob import glob

_MASTERS_CDF_PATH = f"{cdaweb_inventory_data_path.get()}/masters_cdf/"
_XML_CATALOG_PATH = f"{cdaweb_inventory_data_path.get()}/all.xml"


def _ensure_path_exists(path: str):
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


def _clean_master_cdf_folder():
    _ensure_path_exists(_MASTERS_CDF_PATH)
    cdf_files = glob(f"{_MASTERS_CDF_PATH}/*.cdf")
    for cdf_file in cdf_files:
        os.remove(cdf_file)


def _download_and_extract_master_cdf(masters_url: str):
    with NamedTemporaryFile('wb') as master_archive:
        master_archive.write(requests.get(masters_url).content)
        master_archive.flush()
        tar = tarfile.open(master_archive.name)
        tar.extractall(_MASTERS_CDF_PATH)


def update_master_cdf(masters_url: str = "https://spdf.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/master.tar"):
    last_modified = requests.head(masters_url).headers['last-modified']
    if index.get("cdaweb-inventory", "masters-last-modified", "") != last_modified:
        _clean_master_cdf_folder()
        _download_and_extract_master_cdf(masters_url)
        index.set("cdaweb-inventory", "masters-last-modified", last_modified)


def update_xml_catalog(xml_catalog_url: str = "https://spdf.gsfc.nasa.gov/pub/catalogs/all.xml"):
    last_modified = requests.head(xml_catalog_url).headers['last-modified']
    if index.get("cdaweb-inventory", "xml_catalog-last-modified", "") != last_modified:
        _ensure_path_exists(_XML_CATALOG_PATH)
        with open(_XML_CATALOG_PATH, 'w') as f:
            f.write(requests.get(xml_catalog_url).text)
        index.set("cdaweb-inventory", "xml_catalog-last-modified", last_modified)


def build_inventory(xml_catalog_url: str = "https://spdf.gsfc.nasa.gov/pub/catalogs/all.xml",
                    masters_url: str = "https://spdf.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/master.tar"):
    update_xml_catalog(xml_catalog_url)
    t = load_xml_catalog(_XML_CATALOG_PATH)
    update_master_cdf(masters_url)
    update_tree(master_cdf_dir=_MASTERS_CDF_PATH)
    return t
