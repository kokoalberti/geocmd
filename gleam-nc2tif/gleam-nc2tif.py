import os
import sys
import argparse
import csv
import zipfile
import numpy as np

from datetime import datetime, timedelta
from netCDF4 import Dataset
from osgeo import gdal, gdal_array, osr


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Converts a GLEAM NetCDF file "
                                                 "to a georeferenced GTiff.")
    parser.add_argument('file', metavar='FILE', type=str, 
                                help='GLEAM NetCDF File')

    parser.add_argument('target', metavar='TARGET', help='Output filename')

    parser.add_argument('--monthly', help='Output file for monthly average')


    args = parser.parse_args()
    if not os.path.isfile(args.file):
        print("Specified FILE does not exist.")
        sys.exit(1)

    # Open NetCDF file
    try:
        print(f"Loading {args.file}")
        nc = Dataset(args.file, "r")
    except:
        print("Failed to load NetCDF dataset.")
        sys.exit(1)

    # Find GLEAM variable and load it
    data = None
    dataset_name = None
    gleam_variables = {'E','Ep','Ei','Eb','Es','Et','Ew','S','SMroot','SMsurf'}
    variable_names = gleam_variables.intersection(nc.variables.keys())

    if len(variable_names) == 0:
        print("No GLEAM variables found in this NetCDF file. Are you sure it" +
              "is a GLEAM file?")
        sys.exit(1)

    for variable_name in variable_names:
        # Obtain the array
        data = nc.variables[variable_name][:,:,:].astype('float32')
        # Rotate the last 2 axes by 90 degrees
        data = np.rot90(data, k=1, axes=(1,2))
        # Flip over the first axis
        data = np.flip(data, axis=1)
        # Extract name of the variable
        dataset_name = nc.variables[variable_name].standard_name
    print(f"Using NetCDF variable '{variable_name}' ({dataset_name})")

    # Obtain timestamps from 'time' variable
    timestamps = None
    if 'time' in nc.variables:
        epoch = datetime.utcfromtimestamp(0)
        timestamps = [epoch + timedelta(days=days) 
                          for days in nc.variables['time'][:]]

    # Initialize the output GTiff file
    drv = gdal.GetDriverByName('GTiff')
    type_code = gdal_array.NumericTypeCodeToGDALTypeCode(data.dtype)
    opts = ('COMPRESS=LZW', 'PREDICTOR=2', 'TILED=YES', 'NUM_THREADS=ALL_CPUS')
    geotransform = (-180, 0.25, 0, 90, 0, -0.25)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Create the target dataset
    print(f"Converting {args.file} -> {args.target}...")
    ds = drv.Create(args.target, data.shape[2], data.shape[1], data.shape[0], 
                                 type_code, options=opts)

    if ds is None:
        print("Could not create output file. Exiting.")
        sys.exit(1)

    ds.SetGeoTransform(geotransform)
    ds.SetProjection(srs.ExportToWkt())

    # Write the data into the GTiff bands
    for band_number in range(1, data.shape[0]+1):
        band = ds.GetRasterBand(band_number)
        band.SetNoDataValue(-999)
        band_timeinfo = timestamps[band_number-1].strftime("%B %Y")
        band.SetDescription(f"GLEAM {dataset_name} {band_timeinfo}")
        band.WriteArray(data[band_number-1,::])

    ds = None

    # Create a monthly composite if the --monthly option is set
    if args.monthly:
        ds = drv.Create(args.monthly, data.shape[2], data.shape[1], 12, 
                                      type_code, options=opts)
        if ds is None:
            print("Could not create output file for monthly composit. Exiting.")
            sys.exit(1)

        print(f"Creating monthly average composite -> {args.monthly}")
        ds.SetGeoTransform(geotransform)
        ds.SetProjection(srs.ExportToWkt())
        # Create nodata mask
        for m in range(0, 12):
            ix = list(range(m, data.shape[0], 12))
            band = ds.GetRasterBand(m+1)
            band.SetNoDataValue(-999)
            band.SetDescription(f"GLEAM {dataset_name} (Monthly Avg Composite)")
            avg = np.mean(data[ix,:,:], axis=0)
            band.WriteArray(np.ma.filled(avg,-999))
        ds = None

    print("Done!")
