import click
from ctapipe.reco import HillasReconstructor
import pickle
from collections import namedtuple
import astropy.units as u
import pandas as pd
import warnings
from astropy.utils.exceptions import AstropyDeprecationWarning
import numpy as np
from tqdm import tqdm



# do some horrible things to silencece astropy warnings in ctapipe
warnings.filterwarnings('ignore', category=AstropyDeprecationWarning, append=True)
warnings.filterwarnings('ignore', category=FutureWarning, append=True)

SubMomentParameters = namedtuple('SubMomentParameters', 'size,cen_x,cen_y,length,width,psi')


def dummy_function_h_max(self, hillas_dict, subarray, tel_phi):
    return -1


@click.command()
@click.argument(
    'input_file_path', type=click.Path(
        exists=True,
        dir_okay=False,
    ))
@click.argument(
    'output_file_path', type=click.Path(
        exists=False,
        dir_okay=False,
    ))
@click.argument(
    'instrument_description', type=click.Path(
        exists=True,
        dir_okay=False,
    ))
def main(input_file_path, output_file_path, instrument_description):
    instrument = pickle.load(open(instrument_description, 'rb'))

    events = pd.read_csv(input_file_path)

    for array_event_id, group in tqdm(events.groupby('array_event_id')):
        results = reconstruct_direction(array_event_id, group, instrument=instrument)

    df = pd.DataFrame(results)
    df.set_index('array_event_id', inplace=True)

    if 'gamma_prediction' in events.columns:
        df['gamma_prediction_mean'] = events.groupby('array_event_id')['gamma_prediction'].mean()
        df['gamma_prediction_std'] = events.groupby('array_event_id')['gamma_prediction'].std()
    if 'gamma_energy_prediction' in events.columns:
        df['gamma_energy_prediction_mean'] = events.groupby('array_event_id')['gamma_energy_prediction'].mean()
        df['gamma_energy_prediction_std'] = events.groupby('array_event_id')['gamma_energy_prediction'].std()

    df.to_csv(output_file_path, index=False)



def reconstruct_direction(array_event_id, group, instrument):

    reco = HillasReconstructor()
    # monkey patch this huansohn. this is super slow otherwise. who needs max h anyways
    reco.fit_h_max = dummy_function_h_max

    params = {}
    pointing_azimuth = {}
    pointing_altitude = {}
    for index, row in group.iterrows():
        tel_id = row.telescope_id
        # the data in each event has to be put inside these namedtuples to call reco.predict
        moments = SubMomentParameters(size=row.intensity, cen_x=row.x * u.m, cen_y=row.y * u.m, length=row.length * u.m, width=row.width * u.m, psi=row.psi * u.rad)
        params[tel_id] = moments
        pointing_azimuth[tel_id] = row.pointing_azimuth * u.rad
        pointing_altitude[tel_id] = row.pointing_altitude * u.rad

    try:
        reconstruction = reco.predict(params, instrument, pointing_azimuth, pointing_altitude)
    except NameError:
        return {'alt_prediction': np.nan,
                'az_prediction': np.nan,
                'core_x_prediction': np.nan,
                'core_y_prediction': np.nan,
                'array_event_id': array_event_id,
        }

    if reconstruction.alt.si.value == np.nan:
        print('Not reconstructed')
        print(params)

    return {'alt_prediction': ((np.pi / 2) - reconstruction.alt.si.value),  # TODO srsly now? FFS
            'az_prediction': reconstruction.az.si.value,
            'core_x_prediction': reconstruction.core_x.si.value,
            'core_y_prediction': reconstruction.core_y.si.value,
            'array_event_id': array_event_id,
            # 'h_max_prediction': reconstruction.h_max.si.value
            }


if __name__ == '__main__':
    main()
