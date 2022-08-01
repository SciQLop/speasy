from astroquery.utils.tap.core import TapPlus
from .indexes import CSADatasetIndex, CSAParameterIndex


def build_inventory(tapurl="https://csa.esac.esa.int/csa-sl-tap/tap/"):
    CSA = TapPlus(url=tapurl)
    datasets = CSA.launch_job_async("SELECT * FROM csa.v_dataset").get_results()
    colnames = datasets.colnames
    for d in datasets:
        CSADatasetIndex(**{cname: d[cname] for cname in colnames})

    parameters = CSA.launch_job_async("SELECT * FROM csa.v_parameter WHERE data_type='Data'").get_results()
    colnames = parameters.colnames
    for c in parameters:
        CSAParameterIndex(**{cname: c[cname] for cname in colnames})
