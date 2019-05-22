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

    parser.add_argument('dir', metavar='OUTPUT_DIRECTORY', type=str, 
                                help='Output directory')
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print("Specified OUTPUT_DIRECTORY is not a directory.")
        sys.exit(1)

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
    variable_names = set(('E','Ep','Ei','Eb','Es','Et','Ew','S','SMroot','SMsurf')).intersection(nc.variables.keys())

    if len(variable_names) == 0:
        print("No GLEAM variables found in this NetCDF file. Are you sure it" +
              "is a GLEAM file?")
        sys.exit(1)

    for variable_name in variable_names:
        data = nc.variables[variable_name][:,:,:].astype('float32')
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

    # Beware: data.shape is still rotated/mirrored! This is only corrected 
    # on the fly when writing the band.So still flipping the rows/cols in the 
    # drv.Create(...) dataset creation.
    (root, ext) = os.path.splitext(os.path.split(args.file)[-1])
    target = os.path.join(args.dir, root+'.tif')
    print(f"Converting {args.file} -> {target}...")
    ds = drv.Create(target, data.shape[1], data.shape[2], data.shape[0], 
                            type_code, options=opts)

    ds.SetGeoTransform(geotransform)
    ds.SetProjection(srs.ExportToWkt())

    # Update some metadata so we know how this file came to be.
    metadata = {
        'X_CONVERSION_NOTICE': "Converted to GTiff with 'gleam-nc2tif' from " \
                               "https://github.com/kokoalberti/geocmd/gleam-" \
                               "nc2tif/",
        'X_ORIGINAL_FILENAME': os.path.split(args.file)[-1],
        'X_MORE_INFO': "See http://gleam.eu for info on the GLEAM dataset."
    }
    ds.SetMetadata(metadata)

    # Write the data into the GTiff bands
    for band_number in range(1, data.shape[0]+1):
        band = ds.GetRasterBand(band_number)
        band.SetNoDataValue(-999)
        band_timeinfo = timestamps[band_number-1].strftime("%B %Y")
        band.SetDescription(f"GLEAM {dataset_name} {band_timeinfo}")
        band_array = data[band_number-1,::]
        band_array = np.rot90(band_array)
        band_array = np.flip(band_array, 0)
        band.WriteArray(band_array)

    ds = None
    print("Done!")
