#!/usr/bin/env python

import os
import sys
import logging

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.hierarchy
import mapzen.whosonfirst.spatial.postgres

if __name__ == '__main__':

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-D', '--data-root', dest='data_root', action='store', default='/usr/local/data', help='...')
    opt_parser.add_option('-R', '--repo', dest='repo', action='store', default='whosonfirst-data', help='...')

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
    ancs = mapzen.whosonfirst.hierarchy.ancestors(spatial_client=pg_client)

    rebuild_feature = True
    rebuild_descendants = True

    rebuild_kwargs = {
        "rebuild_feature": rebuild_feature,
        "rebuild_descendants": rebuild_descendants,
        "ensure_hierarchy": True,
        "data_root": options.data_root,
        "debug": options.debug,
        "skip_check": True,
    }

    for path in args:

        feature = mapzen.whosonfirst.utils.load_file(path)
        ancs.rebuild_and_export(feature, **rebuild_kwargs)
                
