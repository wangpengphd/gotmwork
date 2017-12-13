; This script reads in net longwave flux, sensible heat flux and
; latent heat flux from OCSPapa and add them together. The sum is
; required in GOTM as heatflux.
;
; Qing Li, 20171108

begin
    dataDir = "/Users/qingli/data/OCSPapa/2016/"
    qlatfile = "qlat50n145w_hr.cdf"
    qsenfile = "qsen50n145w_hr.cdf"
    lwnetfile = "lwnet50n145w_hr.cdf"
    outFile = "heatflux_hr.nc"
    f_qlat = addfile(dataDir+qlatfile, "r")
    qlat = f_qlat->QL_137
    time = f_qlat->time
    depth = f_qlat->depth
    lat = f_qlat->lat
    lon = f_qlat->lon
    f_qsen = addfile(dataDir+qsenfile, "r")
    qsen = f_qsen->QS_138
    f_lwnet = addfile(dataDir+lwnetfile, "r")
    lwnet = f_lwnet->LWN_1136

    HFLUX = -lwnet-qsen-qlat
    HFLUX!0 = "time"
    HFLUX&time = time
    HFLUX!1 = "depth"
    HFLUX&depth = depth
    HFLUX!2 = "lat"
    HFLUX&lat = lat
    HFLUX!3 = "lon"
    HFLUX&lon = lon
    HFLUX@long_name = "Heat flux (Sum of sensible, latent and longwave, negative for net outgoing)"
    HFLUX@units = "W m-2"

    vmissing = 1.e+35
    system("rm -rf "+dataDir+outFile)
    out = addfile(dataDir+outFile, "c")
    out@history = "Generated from "+lwnetfile+", "+qsenfile+" and "+qlatfile
    out@author = "Qing Li"
    out@code = "ocspapa_heatflux.ncl"
    out@missing_value = f_qlat@missing_value
    out@_FillValue = f_qlat@_FillValue
    out->HFLUX = HFLUX
    out->time = time
    out->depth = depth
    out->lat = lat
    out->lon = lon
end