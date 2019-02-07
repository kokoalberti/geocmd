"""
Download script for Sentinel 2 Cloudless tiles by EOX.

TODO: - use argparse to for input
      - validate inputs
      - cleanup
"""

import sys
import os
import tilematrix
import boto3
import click

from shapely.geometry import box

if __name__ == '__main__':
    geom = box(14.0, 65.7, 19.8, 68.7) # our bounding box in lat-lng coords
    zoom = 13 # tile zoom level we want
    output_dir = 'tiles_superhi'
    grid_file = os.path.join(output_dir, 'grid.csv')

    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket('eox-s2maps')
    s3_options = {'RequestPayer':'requester'}

    tile_pyramid = tilematrix.TilePyramid("geodetic", metatiling=2)
    tiles = list(tile_pyramid.tiles_from_geom(geom, zoom))
    num_tiles = len(tiles)

    if not click.confirm("Going to create {} tiles. Continue?".format(num_tiles),
                         default=True):
        sys.exit(1)

    try: os.makedirs(output_dir)
    except: pass

    f = open(grid_file, 'w')
    f.write('geom;zoom;row;col\n')
    with click.progressbar(tiles) as bar:
        for tile in bar:
            key = 'tiles/{}/{}/{}.tif'.format(tile.zoom, tile.row, tile.col)
            filename = os.path.join(output_dir, 'tile_{}_{}_{}.tif'.format(tile.zoom, tile.row, tile.col))
            s3_bucket.download_file(key, filename, s3_options)
            f.write('{};{};{};{}\n'.format(tile.bbox(), tile.zoom, tile.row, tile.col))
    f.close()



