#!/usr/bin/env python

import os
import sys
import logging

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.placetypes
import mapzen.whosonfirst.hierarchy
import mapzen.whosonfirst.spatial.postgres

if __name__ == '__main__':

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-D', '--data-root', dest='data_root', action='store', default='/usr/local/data', help='...')
    opt_parser.add_option('-R', '--repo', dest='repo', action='store', default='whosonfirst-data', help='...')

    opt_parser.add_option('-p', '--placetype', dest='placetype', action='store', default=None, help='...')

    opt_parser.add_option('-d', '--debug', dest='debug', action='store_true', default=False, help='...')
    opt_parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Be chatty (default is false)')

    options, args = opt_parser.parse_args()

    if options.debug:
        options.verbose = True

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    pg_client = mapzen.whosonfirst.spatial.postgres.postgis()

    kwargs = {
        'filters': {
            'is_superseded': 0,
            'is_deprecated': 0,
        },
        'check_centroid': True
    }
    
    if options.placetype:

        pt = mapzen.whosonfirst.placetypes.placetype(options.placetype)
        kwargs['filters']['placetype_id'] = pt.id()

    for path in args:

        feature = mapzen.whosonfirst.utils.load_file(path)

        for row in pg_client.intersects(feature, **kwargs):
            print "%s (%s) %s" % (row[0], row[1], row[3])
                
