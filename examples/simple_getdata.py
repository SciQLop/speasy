import spwc
from datetime import datetime
# A simple example with ACE IMF data
ace_mag = spwc.get_data('amda/imf', datetime(2016,6,2), datetime(2016,6,5))
ace_mag.plot()
