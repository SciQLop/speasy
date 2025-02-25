import os
import tarfile
from glob import glob
from tempfile import TemporaryDirectory

from speasy.core import http, any_files
from ._cdf_masters_parser import update_tree
from ._xml_catalogs_parser import load_xml_catalog
from ....config import cdaweb as cda_cfg
from ....core.index import index
from ....core.inventory.indexes import SpeasyIndex, to_dict, from_dict

_MASTERS_CDF_PATH = f"{cda_cfg.inventory_data_path()}/masters_cdf/"
_XML_CATALOG_PATH = f"{cda_cfg.inventory_data_path()}/all.xml"

_CDAWEB_INVENTORY_ = "cdaweb-inventory"
_CDAWEB_INVENTORY_TREE_ = "tree_v2"
_CDAWEB_INVENTORY_LAST_MODIFIED_MASTERS_ = "masters-last-modified"
_CDAWEB_INVENTORY_LAST_MODIFIED_XML_ = "last_modified_xml"


def _ensure_path_exists(path: str):
    dirname = os.path.dirname(path)
    os.makedirs(dirname, exist_ok=True)


def _clean_master_cdf_folder():
    _ensure_path_exists(_MASTERS_CDF_PATH)
    cdf_files = glob(f"{_MASTERS_CDF_PATH}/*.cdf")
    for cdf_file in cdf_files:
        os.remove(cdf_file)


def _download_and_extract_master_cdf(masters_url: str):
    with TemporaryDirectory() as tmp_path:
        with open(f"{tmp_path}/masters.tar", 'wb') as master_archive:
            master_archive.write(any_files.any_loc_open(masters_url).read())
        tar = tarfile.open(f"{tmp_path}/masters.tar")
        tar.extractall(_MASTERS_CDF_PATH)
        tar.close()


def update_master_cdf(masters_url: str = "https://spdf.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/master.tar"):
    last_modified = http.head(masters_url).headers['last-modified']
    if index.get(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_LAST_MODIFIED_MASTERS_, "") != last_modified:
        _clean_master_cdf_folder()
        _download_and_extract_master_cdf(masters_url)
        index.set(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_LAST_MODIFIED_MASTERS_, last_modified)
        return True
    return False


def update_xml_catalog(xml_catalog_url: str = "https://spdf.gsfc.nasa.gov/pub/catalogs/all.xml"):
    last_modified = http.head(xml_catalog_url).headers['last-modified']
    if index.get(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_LAST_MODIFIED_XML_, "") != last_modified:
        _ensure_path_exists(_XML_CATALOG_PATH)
        with open(_XML_CATALOG_PATH, 'w') as f:
            f.write(http.get(xml_catalog_url).text)
            index.set(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_LAST_MODIFIED_XML_, last_modified)
            return True
    return False


def build_inventory(root: SpeasyIndex = None, xml_catalog_url: str = "https://spdf.gsfc.nasa.gov/pub/catalogs/all.xml",
                    masters_url: str = "https://spdf.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/master.tar"):
    needs_rebuild = update_xml_catalog(xml_catalog_url)
    needs_rebuild |= update_master_cdf(masters_url)
    if needs_rebuild or not index.contains(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_TREE_):
        root = load_xml_catalog(xml_file_path=_XML_CATALOG_PATH, root=root)
        update_tree(root=root, master_cdf_dir=_MASTERS_CDF_PATH)
        index.set(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_TREE_, to_dict(root, version=2))
    else:
        t = from_dict(index.get(_CDAWEB_INVENTORY_, _CDAWEB_INVENTORY_TREE_), version=2)
        root.__dict__ = t.__dict__
    return root
