from datetime import datetime
import pandas as pds
import requests


class cdaweb:
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"

    def get_dataviews(self):
        resp = requests.get(self.__url + '/dataviews', headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        dataviews = [dv['Id'] for dv in resp.json()['DataviewDescription']]
        return dataviews

    def get_instruments(self, dataview='sp_phys', observatory=None, instrumentType=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        resp = requests.get(self.__url + f'/dataviews/{dataview}/instruments?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        instruments = [instrument for instrument in resp.json()['InstrumentDescription'] if
                       instrument['Name'] is not '']
        return instruments

    def get_datasets(self, dataview='sp_phys', observatoryGroup=None, instrumentType=None, observatory=None,
                     instrument=None,
                     startDate=None, stopDate=None, idPattern=None, labelPattern=None, notesPattern=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if observatoryGroup is not None:
            args.append(f'observatoryGroup={observatoryGroup}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        if instrument is not None:
            args.append(f'instrument={instrument}')
        if startDate is not None:
            args.append(f'startDate={startDate}')
        if stopDate is not None:
            args.append(f'stopDate={stopDate}')
        if idPattern is not None:
            args.append(f'idPattern={idPattern}')
        if labelPattern is not None:
            args.append(f'labelPattern={labelPattern}')
        if notesPattern is not None:
            args.append(f'notesPattern={notesPattern}')

        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        datasets = [dataset for dataset in resp.json()['DatasetDescription']]
        return datasets

    def get_variables(self, dataset, dataview='sp_phys'):
        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets/{dataset}/variables',
                            headers={"Accept": "application/json"})

        if not resp.ok:
            return None
        variables = [varaible for varaible in resp.json()['VariableDescription']]
        return variables

    def get_variable(self, dataset, variable, tstart, tend):
        if type(tstart) is datetime:
            tstart, tend = tstart.strftime('%Y%m%dT%H%M%SZ'), tend.strftime('%Y%m%dT%H%M%SZ')
        resp = requests.get(
            f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{tstart},{tend}/{variable}?format=csv",
            headers={"Accept": "application/json"})
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return pds.read_csv(resp.json()['FileDescription'][0]['Name'], comment='#', index_col=0,
                            infer_datetime_format=True, parse_dates=True)
