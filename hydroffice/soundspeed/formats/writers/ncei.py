from __future__ import absolute_import, division, print_function, unicode_literals

import numpy as np
import netCDF4
import os
import calendar
import datetime as dt
import logging

logger = logging.getLogger(__name__)

from ... import __version__ as ssp_version
from ... import __doc__ as ssp_name
from .abstract import AbstractWriter
from ...profile.dicts import Dicts


class Ncei(AbstractWriter):
    """NCEI binary writer

    Useful links:
    - http://www.nodc.noaa.gov/data/formats/netcdf/v2.0/profileOrthogonal.cdl
    - http://puma.nerc.ac.uk/cgi-bin/cf-checker.pl
    """

    def __init__(self):
        super(Ncei, self).__init__()
        self.desc = "NCEI"
        self._ext.add('nc')
        self.root_group = None

    def write(self, ssp, data_path, data_file=None, data_append=False):
        """Writing profile data"""
        logger.debug('*** %s ***: start' % self.driver)

        self.ssp = ssp

        # define the output file path
        if data_file:
            if len(data_file.split('.')) == 1:
                data_file += (".%s" % list(self.ext)[0])
            file_path = os.path.join(data_path, data_file)
        else:
            if self.ssp.cur.meta.original_path:
                data_file = os.path.basename(self.ssp.cur.meta.original_path) + '.' + list(self.ext)[0]
            else:
                data_file = 'output.' + list(self.ext)[0]
            data_path = os.path.join(data_path, self.name.lower())
            if not os.path.exists(data_path):
                os.makedirs(data_path)
            file_path = os.path.join(data_path, data_file)
        logger.info("output file: %s" % file_path)

        # create the file
        self.root_group = netCDF4.Dataset(file_path, 'w', format='NETCDF4')

        self._write_header()
        self._write_body()

        self.finalize()

        logger.debug('*** %s ***: done' % self.driver)
        return True

    def _write_header(self):
        """Write header"""
        logger.debug('generating header')

        # set the 'z' dimension and the number of profiles (always 1)
        self.root_group.createDimension(b'z', np.sum(self.ssp.cur.data_valid))
        self.root_group.createDimension(b'profile', 1)

        # var: profile
        # RECOMMENDED - If using the attribute below: cf_role. Data type can be whatever is appropriate for the
        # unique feature type.
        profile_str = "%s %.7f %.7s %s" % (self.ssp.cur.meta.utc_time.isoformat(), self.ssp.cur.meta.longitude,
                                           self.ssp.cur.meta.latitude, self.ssp.cur.meta.vessel)
        default_profile_str_length = 64
        profile_str_length = max(default_profile_str_length, len(profile_str))
        self.root_group.createDimension(b'profile_id_length', profile_str_length)
        profile = self.root_group.createVariable(b'profile', b'S1', (b'profile', b'profile_id_length',))
        profile[:] = netCDF4.stringtoarr(profile_str, profile_str_length)
        profile.long_name = b'Unique identifier for each feature instance'  # RECOMMENDED
        profile.cf_role = b'profile_id'  # RECOMMENDED

        # var: time
        # Depending on the precision used for the variable, the data type could be int or double instead of float.
        time = self.root_group.createVariable(b'time', b'i4', (b'profile',), fill_value=0.0)
        time[:] = calendar.timegm(self.ssp.cur.meta.utc_time.timetuple())
        time.long_name = b'cast time'  # RECOMMENDED - Provide a descriptive, long name for this variable.
        time.standard_name = b'time'  # REQUIRED - Do not change
        time.units = b'seconds since 1970-01-01 00:00:00'  # REQUIRED - Use approved CF convention with approved UDUNITS.
        # time.calendar = 'julian'  # REQUIRED    - IF the calendar is not default calendar, which is "gregorian".
        time.axis = b'T'  # REQUIRED    - Do not change.
        # time._FillValue = 0.0  # REQUIRED  if there could be missing values in the data. >> set at var creation
        time.ancillary_variables = b''  # RECOMMENDED - List other variables providing information about this variable.
        time.comment = b''  # RECOMMENDED - Add useful, additional information here.

        # var: lat
        # depending on the precision used for the variable, the data type could be int, float or double.
        lat = self.root_group.createVariable(b'lat', b'f8', (b'profile',), fill_value=180.0)
        lat[:] = self.ssp.cur.meta.latitude
        lat.long_name = b'latitude'  # RECOMMENDED - Provide a descriptive, long name for this variable.
        lat.standard_name = b'latitude'  # REQUIRED - Do not change.
        lat.units = b'degrees_north'  # REQUIRED - CF recommends degrees_north, but at least must use UDUNITS.
        lat.axis = b'Y'  # REQUIRED - Do not change.
        lat.valid_min = -90.0  # RECOMMENDED - Replace with correct value.
        lat.valid_max = 180.0  # RECOMMENDED - Replace with correct value.
        # lat._FillValue = 180.0  # REQUIRED if there could be missing values in the data.
        lat.ancillary_variables = b''  # RECOMMENDED - List other variables providing information about this variable.
        lat.comment = b''  # RECOMMENDED - Add useful, additional information here.

        # var: lon
        # Depending on the precision used for the variable, the data type could be int, float or double.
        lon = self.root_group.createVariable(b'lon', b'f8', (b'profile',), fill_value=360.0)
        lon[:] = self.ssp.cur.meta.longitude
        lon.long_name = b'longitude'  # RECOMMENDED
        lon.standard_name = b'longitude'  # REQUIRED - This is fixed, do not change.
        lon.units = b'degrees_east'  # REQUIRED - CF recommends degrees_east, but at least use UDUNITS.
        lon.axis = b'X'  # REQUIRED - Do not change.
        lon.valid_min = -180.0  # RECOMMENDED - Replace this with correct value.
        lon.valid_max = 360.0  # RECOMMENDED - Replace this with correct value.
        # lon:_FillValue = 360.0 # REQUIRED if there could be missing values in the data.
        lon.ancillary_variables = b''  # RECOMMENDED - List other variables providing information about this variable.
        lon.comment = b''  # RECOMMENDED - Add useful, additional information here.

        # var: crs
        # RECOMMENDED - A container variable storing information about the grid_mapping.
        # All the attributes within a grid_mapping variable are described in:
        # - http://cfconventions.org/Data/cf-conventions/cf-conventions-1.6/build/cf-conventions.html#grid-mappings-
        # and-projections.
        # For all the measurements based on WSG84, the default coordinate system used for GPS measurements,
        # the values shown here should be used.
        crs = self.root_group.createVariable(b'crs', b'f8', (b'profile',))
        crs[:] = 4326.0
        crs.grid_mapping_name = b'latitude_longitude'  # RECOMMENDED
        crs.epsg_code = b'EPSG:4326'  # RECOMMENDED - European Petroleum Survey Group code for the grid mapping name.
        crs.semi_major_axis = 6378137.0  # RECOMMENDED
        crs.inverse_flattening = 298.257223563  # RECOMMENDED

        # global attributes:
        self.root_group.ncei_template_version = b'NCEI_NetCDF_Profile_Orthogonal_Template_v2.0'  # REQUIRED(NCEI)
        self.root_group.featureType = b'profile'  # REQUIRED - CF attribute for identifying the featureType.(CF)
        # HIGHLY RECOMMENDED - Provide a useful title for the data in the file.(ACDD)
        self.root_group.title = b'Sound speed profile'
        # HIGHLY RECOMMENDED - Provide a useful summary or abstract for the data in the file.(ACDD)
        self.root_group.summary = b''
        # HIGHLY RECOMMENDED - A comma separated list of keywords coming from the keywords_vocabulary.(ACDD)
        self.root_group.keywords = b''
        # HIGHLY RECOMMENDED - A comma separated list of the conventions being followed. Always try to use latest
        # version.(CF / ACDD)
        self.root_group.Conventions = b'CF-1.6, ACDD-1.3'
        # RECOMMENDED - Creation date of this version of the data(netCDF).  Use ISO 8601:2004 for date and time. (ACDD)
        self.root_group.date_created = b'%s' % dt.datetime.utcnow().isoformat()
        # SUGGESTED - The data type, as derived from Unidata's Common Data Model Scientific Data types and understood
        # by THREDDS. (ACDD)
        self.root_group.cdm_data_type = b'Station'
        # RECOMMENDED - Provide useful additional information here.(CF)
        self.root_group.comment = b'Created using HydrOffice %s v.%s' % (ssp_name, ssp_version)
        # SUGGESTED - Published or web - based references that describe the data or methods used to produce it.
        # Recommend URIs(such as a URL or DOI)
        self.root_group.references = b'https://www.hydroffice.org/soundspeed/'
        # SUGGESTED - Name of the platform(s) that supported the sensor data used to create this data set or product.
        # Platforms can be of any type, including satellite, ship, station, aircraft or other.(ACDD)
        self.root_group.platform = b'%s' % self.ssp.cur.meta.vessel
        # RECOMMENDED - The name of the project(s) principally responsible for originating this data.
        # Multiple projects can be separated by commas.(ACDD)
        self.root_group.project = b'%s' % self.ssp.cur.meta.project
        # RECOMMENDED - The method of production of the original data.(CF)
        self.root_group.source = b'sensor: %s, probe type: %s' % (self.ssp.cur.meta.sensor, self.ssp.cur.meta.probe)

    def _write_body(self):
        logger.debug('generating body')

        # valid indices
        vi = self.ssp.cur.data_valid

        # var: temperature
        if np.mean(self.ssp.cur.data.temp[vi]) != 0.0:
            temperature = self.root_group.createVariable(b'temperature', b'f4', (b'profile', b'z',))
            temperature[:] = self.ssp.cur.data.temp[vi]
            # RECOMMENDED - Provide a descriptive, long name for this variable.
            temperature.long_name = b'temperature in sea water'
            # REQUIRED - If using a CF standard name and a suitable name exists in the CF standard name table.
            temperature.standard_name = b'sea_water_temperature'
            temperature.units = b'degree_C'  # REQUIRED - Use UDUNITS compatible units.

        # var: salinity
        if np.mean(self.ssp.cur.data.sal[vi]) != 0.0:
            salinity = self.root_group.createVariable(b'salinity', b'f4', (b'profile', b'z',))
            salinity[:] = self.ssp.cur.data.sal[vi]
            # RECOMMENDED - Provide a descriptive, long name for this variable.
            salinity.long_name = b'salinity in sea water'
            # REQUIRED - If using a CF standard name and a suitable name exists in the CF standard name table.
            salinity.standard_name = b'sea_water_salinity'
            salinity.units = b'1e-3'  # REQUIRED - Use UDUNITS compatible units.

        # var: sound speed
        if np.mean(self.ssp.cur.data.speed[vi]) != 0.0:
            sound_speed = self.root_group.createVariable(b'sound_speed', b'f4', (b'profile', b'z',))
            sound_speed[:] = self.ssp.cur.data.speed[vi]
            # RECOMMENDED - Provide a descriptive, long name for this variable.
            sound_speed.long_name = b'sound speed in sea water'
            # REQUIRED - If using a CF standard name and a suitable name exists in the CF standard name table.
            sound_speed.standard_name = b'sea_water_speed'
            sound_speed.units = b'm s-1'  # REQUIRED - Use UDUNITS compatible units.

        self.root_group.close()