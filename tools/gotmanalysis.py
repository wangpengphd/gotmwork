import numpy as np
from netCDF4 import Dataset

# gravitational acceleration (m/s^2)
g = 9.81
# specific heat of seawater (J/kg/degC)
cp = 3985.0
# Von Karman constant
kappa = 0.4
# reference density of seawater (kg/m^3)
rho_0 = 1027.0
# reference salinity (psu)
S_0 = 35.0
# reference temperature (degC)
T_0 = 10.0
# constant thermal expansion coefficient (1/degC)
alpha_0 = 1.65531e-4
# constant saline contraction coefficient (1/psu)
beta_0 = 7.59494e-4

class GOTMOutputData(object):

    """GOTM Output data object"""

    def __init__(self, path):
        """Initialize the data

        :path: Path to the netCDF file

        """
        # path of data
        self._path = path
        # netCDF4 Dataset
        self.dataset = Dataset(self._path, 'r')
        # latitude
        self.lat = self.dataset.variables['lat'][:]
        # Coriolis parameter
        self.f = 4.*np.pi/86400*np.sin(self.lat*np.pi/180.)
        # longitude
        self.lon = self.dataset.variables['lon'][:]
        # time
        self.time = self.dataset.variables['time']
        # list of dimensions
        self.list_dimensions = list(self.dataset.dimensions.keys())
        # list of variables
        list_variables = list(self.dataset.variables.keys())
        self.list_variables = [x for x in list_variables if x not in self.list_dimensions]
        # list of time series and profiles
        self.list_timeseries = []
        self.list_profiles = []
        for var in self.list_variables:
            ndim = self.dataset.variables[var].ndim
            if ndim == 4:
                self.list_profiles.append(var)
            elif ndim == 3:
                self.list_timeseries.append(var)
            else:
                pass
        # update list of variables to include the derived ones
        self.list_variables = self.list_variables + self._get_derived_variable(list_keys=True)

    def read_profile(self, var, tidx_start=None, tidx_end=None):
        """Return profile variable and z (fixed in time)

        :var: (str) variable name
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) profile, z

        """
        if var in self.list_profiles:
            dat = self.dataset.variables[var][tidx_start:tidx_end,:,0,0]
            coord = infile.variables[var].coordinates
            if 'zi' in coord:
                z = infile.variables['zi'][0,:,0,0]
            elif 'z' in coord:
                z = infile.variables['z'][0,:,0,0]
            else:
                raise AttributeError('z coordinate not fould.')
        else:
            dat, z = self._get_derived_variable(var)(tidx_start=tidx_start, tidx_end=tidx_end)
        return dat, z

    def read_timeseries(self, var, tidx_start=None, tidx_end=None):
        """Return timeseries of variable [var]

        :var: (str) variable name
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) time series

        """
        if var in self.list_timeseries:
            dat = self.dataset.variables[var][tidx_start:tidx_end,0,0]
        else:
            dat = self._get_derived_variable(var)(tidx_start=tidx_start, tidx_end=tidx_end)
        return dat

    def mean_profile(self, var, tidx_start=None, tidx_end=None):
        """Return the mean profile of variable [var]

        :var: (str) variable name
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) profile, z

        """
        dat, z = self.read_profile(var, tidx_start=tidx_start, tidx_end=tidx_end)
        mdat = np.mean(dat, axis=0)
        return mdat, z

    def mean_state(self, var, tidx_start=None, tidx_end=None):
        """Return the mean value of timeseries of variable [var]

        :var: (str) variable name
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) profile, z

        """
        dat = self.read_timeseries(var, tidx_start=tidx_start, tidx_end=tidx_end)
        mdat = np.mean(dat, axis=0)
        return mdat

    def _get_derived_variable(self, name=None, list_keys=False):
        """Find the derived variable

        :name: (str) variable name
        :returns: (function) corresponding function

        """
        switcher = {
                'LaTurb': self._get_la_turb,
                'LaSL': self._get_la_sl,
                'hoLmo': self._get_h_over_lmo,
                'buoyancy': self._get_buoyancy,
                'spice': self._get_spice,
                'bflux': self._get_bflux,
                'dPEdt': self._get_dpedt,
                'mixEf1': self._get_dpedt_over_ustar3,
                'mld_maxNsqr': self._get_mld_maxNsqr,
                'mld_deltaT': self._get_mld_deltaT,
                'mld_deltaR': self._get_mld_deltaR
                }
        if list_keys:
            return list(switcher.keys())
        elif name in switcher.keys():
            return switcher.get(name)
        else:
            raise ValueError('Variable \'{}\' not found.'.format(name))

    def _get_la_turb(self, tidx_start=None, tidx_end=None):
        """Find the turbulent Langmuir number defined as
           La_t = sqrt{u^*/u^S}

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) Langmuir number

        """
        # friction velocity
        ustar = self.dataset.variables['u_taus'][tidx_start:tidx_end,0,0]
        # surface Stokes drift
        usx = self.dataset.variables['u0_stokes'][tidx_start:tidx_end,0,0]
        usy = self.dataset.variables['v0_stokes'][tidx_start:tidx_end,0,0]
        us = np.sqrt(usx**2.+usy**2.)
        # calculate Langmuir number
        la = np.sqrt(ustar/us)
        return la

    def _get_la_sl(self, tidx_start=None, tidx_end=None):
        """Find the surface layer averaged Langmuir number defined as
           La_{SL} = sqrt{u^*/<u^S>_{SL}}, where
           <u^S>_{SL} = int_{-0.2h_b}^0 u^S(z) dz

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) Langmuir number

        """
        # friction velocity
        ustar = self.dataset.variables['u_taus'][tidx_start:tidx_end,0,0]
        # Stokes drift profiles
        ustokes = self.dataset.variables['u_stokes'][tidx_start:tidx_end,:,0,0]
        vstokes = self.dataset.variables['v_stokes'][tidx_start:tidx_end,:,0,0]
        zi = self.dataset.variables['zi'][tidx_start:tidx_end,:,0,0]
        h = self.dataset.variables['h'][tidx_start:tidx_end,:,0,0]
        # boundary layer depth
        hbl = self._get_derived_variable('mld_deltaR')(tidx_start=tidx_start, tidx_end=tidx_end)
        # surface layer: upper 20% of the boundary layer
        hsl = 0.2*hbl
        # loop over time to calculate the surface layer averaged Stokes drift
        # note that zi has indices 0:nlev whereas z has indices 0:nlev-1, this is
        # different from the indices in GOTM
        nt = self.time.shape[0]
        ussl = np.zeros(nt)
        vssl = np.zeros(nt)
        for i in np.arange(nt):
            ihsl = np.argmin(zi[i,:]<hsl[i])
            dzb = zi[i,ihsl]-hsl[i]
            ussl[i] = np.sum(ustokes[i,ihsl:]*h[i,ihsl:])+ustokes[i,ihsl-1]*dzb
            vssl[i] = np.sum(vstokes[i,ihsl:]*h[i,ihsl:])+vstokes[i,ihsl-1]*dzb
        ussl = ussl/np.abs(hsl)
        vssl = vssl/np.abs(hsl)
        # surface layer averaged Langmuir number
        la = np.sqrt(ustar/np.sqrt(ussl**2.+vssl**2.))
        return la

    def _get_bflux(self, tidx_start=None, tidx_end=None):
        """Find the surface buoyancy flux

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) surface buoyancy flux

        """
        # get boundary layer depth
        hbl   = self._get_derived_variable('mld_deltaR')(tidx_start=tidx_start, tidx_end=tidx_end)
        # surface temperature and salinity
        temp0 = self.dataset.variables['temp'][tidx_start:tidx_end,-1,0,0]
        salt0 = self.dataset.variables['salt'][tidx_start:tidx_end,-1,0,0]
        # surface temperature flux
        tflux = self.dataset.variables['heat'][tidx_start:tidx_end,0,0]/cp/rho_0
        # correction for solar radiation
        rad   = self.dataset.variables['rad'][tidx_start:tidx_end,:,0,0]
        z     = self.dataset.variables['z'][tidx_start:tidx_end,:,0,0]
        nt    = self.time.shape[0]
        rflux = np.zeros(nt)
        for i in np.arange(nt):
            ihbl = np.argmin(np.abs(z[i,:]-hbl[i]))
            rflux[i] = rad[i,-1]-rad[i,ihbl]
        tflux = tflux+rflux/cp/rho_0
        # surface salinity flux
        sflux = -(self.dataset.variables['precip'][tidx_start:tidx_end,0,0]
                + self.dataset.variables['evap'][tidx_start:tidx_end,0,0])*salt0
        # surface buoyancy flux (positive for stable condition)
        bflux = g*alpha_0*tflux-g*beta_0*sflux
        return bflux

    def _get_h_over_lmo(self, tidx_start=None, tidx_end=None):
        """Find the stability parameter defined as h/L
           where h is the boundary layer depth
           and L is the Monin–Obukhov length

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) stability parameter

        """
        # get boundary layer depth
        hbl   = self._get_derived_variable('mld_deltaR')(tidx_start=tidx_start, tidx_end=tidx_end)
        # get surface buoyancy flux
        bflux = self._get_bflux(tidx_start=tidx_start, tidx_end=tidx_end)
        # friction velocity
        ustar = self.dataset.variables['u_taus'][tidx_start:tidx_end,0,0]
        # Monin-Obukhov length
        Lmo = ustar**3.0/kappa/bflux
        # filter out zeros
        Lmo = np.ma.array(Lmo, mask=(Lmo==0))
        # h over L
        hoL = -abs(hbl)/Lmo
        return hoL

    def _get_buoyancy(self, tidx_start=None, tidx_end=None):
        """Calculate the buoyancy from temperature and salinity
        assuming linear equation of state

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) buoyancy

        """
        # temperature and salinity
        temp  = self.dataset.variables['temp'][tidx_start:tidx_end,:,0,0]
        salt  = self.dataset.variables['salt'][tidx_start:tidx_end,:,0,0]
        # buoyancy
        buoy  = g*alpha_0*(temp-T_0)-g*beta_0*(salt-S_0)
        # z
        z     = self.dataset.variables['z'][0,:,0,0]
        return buoy, z

    def _get_spice(self, tidx_start=None, tidx_end=None):
        """Calculate the spice from temperature and salinity
        assuming linear equation of state

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) spice

        """
        # temperature and salinity
        temp  = self.dataset.variables['temp'][tidx_start:tidx_end,:,0,0]
        salt  = self.dataset.variables['salt'][tidx_start:tidx_end,:,0,0]
        # spice
        spice  = g*alpha_0*(temp-T_0)+g*beta_0*(salt-S_0)
        # z
        z     = self.dataset.variables['z'][0,:,0,0]
        return spice, z

    def _get_dpedt(self, tidx_start=None, tidx_end=None):
        """Calculate the rate of change in the total potential energy (PE)

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) rate of change in PE

        """
        # time series of potential energy
        epot = self.dataset.variables['Epot'][tidx_start:tidx_end,0,0]
        # time (sec)
        time = self.time[tidx_start:tidx_end]
        # get the time derivative
        nt = time.shape[0]
        dpedt = np.zeros(nt)
        dpedt[1:-1] = (epot[2:]-epot[0:-2])/(time[2:]-time[0:-2])
        dpedt[0] = (epot[1]-epot[0])/(time[1]-time[0])
        dpedt[-1] = (epot[-1]-epot[-2])/(time[-1]-time[-2])
        return dpedt

    def _get_dpedt_over_ustar3(self, tidx_start=None, tidx_end=None):
        """Calculate the bulk rate of change in the total potential
           energy (PE), normalized by firction

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) rate of change in PE

        """
        # rate of potential energy
        dpedt = self._get_dpedt(tidx_start=tidx_start, tidx_end=tidx_end)
        # friction velocity
        ustar = self.dataset.variables['u_taus'][tidx_start:tidx_end,0,0]
        # normalize by rho_0*ustar**3
        bulk_dpedt = dpedt/ustar**3/rho_0
        return bulk_dpedt

    def _get_mld_maxNsqr(self, tidx_start=None, tidx_end=None):
        """Find the mixed layer depth defined as the depth where
           the stratification N^2 reaches its maximum

        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) mixed layer depth

        """
        Nsqr = self.dataset.variables['NN'][tidx_start:tidx_end,:,0,0]
        z = self.dataset.variables['z'][tidx_start:tidx_end,:,0,0]
        time = self.time[tidx_start:tidx_end]
        nt = time.shape[0]
        mld = np.zeros(nt)
        # find the indices where N^2 reaches its maximum
        idx_max = np.argmax(Nsqr, 1)
        for i in np.arange(nt):
            mld[i] = z[i,idx_max[i]]
        return mld

    def _get_mld_deltaT(self, tidx_start=None, tidx_end=None, deltaT=0.2, zRef=-10):
        """Find the mixed layer depth defined as the depth where
           the temperature difference from the reference level first exceed
           a threshold value

        :deltaT: (float, optional) temperature threshold in degree C
        :zRef: (float, optional) depth of the reference level
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) mixed layer depth

        """
        Temp = self.dataset.variables['temp'][tidx_start:tidx_end,:,0,0]
        z = self.dataset.variables['z'][tidx_start:tidx_end,:,0,0]
        time = self.time[tidx_start:tidx_end]
        nt = time.shape[0]
        mld = np.zeros(nt)
        for i in np.arange(nt):
            idx_zref = np.argmin(np.abs(z[i,:]-zRef))
            dTemp = Temp[i,:]-Temp[i,idx_zref]
            # ignore the points above the reference level
            dTemp[idx_zref:] = 99.
            # ignore nan
            dTemp[np.isnan(dTemp)] = 99.
            # find the maximum index (closest to the surface) where the temperature
            # difference is greater than the threshold value
            idxlist = np.where(dTemp<=-deltaT)
            if idxlist[0].size>0:
                idx_min = np.max(idxlist)
                mld[i] = z[i,idx_min]
            else:
                mld[i] = np.min(z[i,:])
        return mld

    def _get_mld_deltaR(self, tidx_start=None, tidx_end=None, deltaR=0.03, zRef=-10):
        """Find the mixed layer depth defined as the depth where
           the potential density difference from the reference level first exceed
           a threshold value

        :deltaR: (float, optional) potential density threshold in kg/m^3
        :zRef: (float, optional) depth of the reference level
        :tidx_start: (int, optional) starting index
        :tidx_end: (int, optional) ending index
        :returns: (numpy array) mixed layer depth

        """
        Rho = self.dataset.variables['rho'][tidx_start:tidx_end,:,0,0]
        z = self.dataset.variables['z'][tidx_start:tidx_end,:,0,0]
        time = self.time[tidx_start:tidx_end]
        nt = time.shape[0]
        mld = np.zeros(nt)
        for i in np.arange(nt):
            idx_zref = np.argmin(np.abs(z[i,:]-zRef))
            dRho = Rho[i,:]-Rho[i,idx_zref]
            # ignore the points above the reference level
            dRho[idx_zref:] = -99.
            # ignore nan
            dRho[np.isnan(dRho)] = -99.
            # find the maximum index (closest to the surface) where the density
            # difference is greater than the threshold value
            idxlist = np.where(dRho>=deltaR)
            if idxlist[0].size>0:
                idx_min = np.max(idxlist)
                mld[i] = z[i,idx_min]
            else:
                mld[i] = np.min(z[i,:])
        return mld
