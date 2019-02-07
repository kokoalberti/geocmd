# -*- coding: utf-8 -*-
"""
Utility program to cut 1024x1024 pixel tiles from a raster image based on a 
vector grid. Then add all the tiles and a KML index file to a zip file to 
produce a Garmin-compatible KMZ file.

Usage: garmin-kmz.py --grid <GRID_FILE> --raster <RASTER_FILE>


"""
import os
import sys
import argparse
import csv
import zipfile

try:
    from osgeo import gdal
except ImportError:
    print("Could not import gdal! Are gdal python bindings installed?")
    sys.exit(1)

if __name__ == '__main__':
    # Parse the command-line arguments
    parser = argparse.ArgumentParser(description="Make a Garmin KMZ custom map")
    parser.add_argument('--grid', help='CSV grid file with to use')
    parser.add_argument('--raster', help='Georeferenced raster file to use')
    args = parser.parse_args()

    # Remove existing 'custom-map.kmz' if it exists
    kmz_file = "custom-map.kmz"
    if os.path.isfile(kmz_file):
        os.remove(kmz_file)

    # Avoid creation of aux.xml files when exporting to JPEG
    gdal.SetConfigOption('GDAL_PAM_ENABLED','NO')

    # Open the grid file and iterate over its entries, creating a list of tile
    # extents that we're going to work with.
    tiles = []
    with open(args.grid) as csvfile:
        reader = csv.DictReader(csvfile)
        for i,row in enumerate(reader):
            # Try to parse the columns, otherwise skip the row
            try:
                bounds = list(map(float, (row['xmin'], 
                                          row['ymin'], 
                                          row['xmax'], 
                                          row['ymax'])))
            except:
                print("Error in row {}: Could not parse. Skip!".format(i))
                continue

            # Verify that the tile is (reasonably) square
            if ((bounds[2] - bounds[0]) - (bounds[3] - bounds[1])) > 0.001:
                print("Error in row {}: Tile is not square. Skip!".format(i))
                continue

            # Append to the list of tiles to process
            tiles.append(bounds)

    # Check that some tiles were actually found
    num_tiles = len(tiles)
    if num_tiles == 0:
        print("No tiles were found. Exiting.")
        sys.exit(1)

    # Check number of tiles is less than 100
    if num_tiles > 100:
        print("Maximum of 100 tiles supported. Exiting.")
        sys.exit(1)

    # Iterate over tiles and apply magic
    print("Creating {} tiles inside {}...".format(num_tiles, kmz_file))
    overlays = ""
    for i, (xmin, ymin, xmax, ymax) in enumerate(tiles):

        # Warping each tile and then translating to JPEG produced better 
        # results than warping the entire input file in an in-memory VRT and 
        # then translating a subset to a JPEG file. So, just resample each 
        # tile individually.
        resampleAlg = 'lanczos'
        outputBounds = (xmin, ymin, xmax, ymax)

        # Execute the warp into an in-memory VRT using gdal.Warp()
        warp = gdal.Warp('', args.raster, dstSRS='EPSG:4326', format='VRT', 
                         outputBounds=outputBounds, resampleAlg=resampleAlg)

        # Write the JPEG tile into the zip/kmz file using gdal.Translate() and 
        # /vsizip/ virtual file system
        zip_filename = '/vsizip/{}/tiles/tile-{}.jpg'.format(kmz_file, i)
        gdal.Translate(zip_filename, warp, format='JPEG')

        # Create the XML for the overlay part in the KML file
        overlays += """
            <GroundOverlay>
                <name>Tile {}</name>
                <drawOrder>30</drawOrder>
                <Icon>
                  <href>tiles/tile-{}.jpg</href>
                </Icon>
                <LatLonBox>
                  <north>{}</north>
                  <south>{}</south>
                  <east>{}</east>
                  <west>{}</west>
                </LatLonBox>
            </GroundOverlay>
        """.format(i, i, ymax, ymin, xmax, xmin)

    # Complete the XML for the KML file
    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>custom-map</name>
    {}
  </Document>
</kml>
    """.format(overlays)

    # Add the KML file to 'doc.kml' in the KMZ archive
    with zipfile.ZipFile(kmz_file, 'a') as kmz:
        kmz.writestr('doc.kml', kml)

    print("Done!")
