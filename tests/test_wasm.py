try:
    from pytest_pyodide import run_in_pyodide
    from pytest_pyodide.decorator import copy_files_to_pyodide
    import pytest

    from glob import glob

    _FILE_PATH = glob("pyodide-dist/speasy*.whl", recursive=True)[0]
    _DEST_PATH = _FILE_PATH.split("/")[-1]


    @pytest.mark.driver_timeout(60 * 2)
    @copy_files_to_pyodide(file_list=[(_FILE_PATH, _DEST_PATH)], install_wheels=True, recurse_directories=True)
    @run_in_pyodide(packages=['micropip', 'pycdfpp'])
    async def test_import_speasy(selenium):
        import speasy as spz
        assert spz.__version__ is not None
        assert spz.core.platform.is_running_on_wasm()


    @pytest.mark.parametrize("product_path", [
        "amda/c1_b_gsm",
        "amda/ace-imf-all",
        "cdaweb/THA_L2_FGM/tha_fgl_gsm",
        "sscweb/moon",
    ])
    @pytest.mark.driver_timeout(60 * 2)
    @copy_files_to_pyodide(file_list=[(_FILE_PATH, _DEST_PATH)], install_wheels=True, recurse_directories=True)
    @run_in_pyodide(packages=['micropip', 'pycdfpp'])
    async def test_simple_query(selenium, product_path):
        import speasy as spz
        v = spz.get_data(product_path, "2020-01-01", "2020-01-02")
        assert v is not None
        assert len(v) > 0


except ImportError:
    print("pytest-pyodide is not installed; skipping Pyodide tests.")
