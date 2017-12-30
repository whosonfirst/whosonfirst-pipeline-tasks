#!/usr/bin/env python

import os
import sys
import logging

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.export
import mapzen.whosonfirst.uri

import mapzen.whosonfirst.hierarchy
import mapzen.whosonfirst.spatial.postgres

if __name__ == "__main__":

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-D', '--data-root', dest='data_root', action='store', default='/usr/local/data', help='... (Default is /usr/local/data)')
    opt_parser.add_option('-R', '--repo', dest='repo', action='store', default='whosonfirst-data', help='... (Default is whosonfirst-data)')

    opt_parser.add_option('-U', '--union', dest='union', action='store_true', default=False, help='... (Default is false)')

    opt_parser.add_option('-d', '--debug', dest='debug', action='store_true', default=False, help='... (Default is false.)')
    opt_parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Be chatty (default is false)')

    opt_parser.add_option('--pgis-host', dest='pgis_host', action='store', default='localhost')
    opt_parser.add_option('--pgis-username', dest='pgis_username', action='store', default='postgres')
    opt_parser.add_option('--pgis-password', dest='pgis_password', action='store', default=None)
    opt_parser.add_option('--pgis-database', dest='pgis_database', action='store', default='whosonfirst')

    options, args = opt_parser.parse_args()

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        
    data_root = options.data_root

    root = os.path.join(data_root, options.repo)
    data = os.path.join(root, "data")
    
    pg_args = {
        "dbname": options.pgis_database,
        "username": options.pgis_username,
        "password": options.pgis_password,
        "host": options.pgis_host,
    }

    pg_client = mapzen.whosonfirst.spatial.postgres.postgis(**pg_args)
    ancs = mapzen.whosonfirst.hierarchy.ancestors(spatial_client=pg_client)

    def cb (feature):

        props = feature["properties"]
        repo = props["wof:repo"]
        
        root = os.path.join(data_root, repo)
        data = os.path.join(root, "data")
        
        exporter = mapzen.whosonfirst.export.flatfile(data)

        if options.debug:
            path = mapzen.whosonfirst.uri.id2abspath(data, props["wof:id"])
            logging.info("WOULD HAVE updated %s (%s)" % (props['wof:name'], path))
        else:
            path = exporter.export_feature(feature)
            logging.info("update %s (%s)" % (props['wof:name'], path))

        return True

    def process (feature):

        kwargs = {
            "data_root": data_root,
            "placetypes": ["venue"],
            "include": ["venue"]
        }
        
        return ancs.rebuild_descendants(feature, cb, **kwargs)

    updated = []

    if options.union:

        logging.warning("Unioning multiple parents is still experimental so be prepared...")

        try:
            import shapely.geometry
        except Exception, e:
            logging.warning("You need to have shapely installed for this to work")
            logging.debug(e)
            sys.exit(1)

        combined = None

        for wofid in args:
            
            feature = mapzen.whosonfirst.utils.load(data, wofid)
            shape = shapely.geometry.asShape(feature["geometry"])
            
            if combined == None:
                combined = shape
            else:
                combined = combined.union(shape)

        combined_geom = shapely.geometry.mapping(combined)

        combined_props = {
            "wof:id": -1,
            "wof:name": "COMBINED"
        }
    
        combined_feature = {
            "type": "Feature",
            "geometry": combined_geom,
            "properties": combined_props
        }

        for repo in process(combined_feature):

            if not repo in updated:
                updated.append(repo)

    else:

        for wofid in args:

            feature = mapzen.whosonfirst.utils.load(data, wofid)
            processed = process(feature)

            if not processed:
                continue

            for repo in processed:

                if not repo in updated:
                    updated.append(repo)

    for repo in updated:
        print repo

    sys.exit(0)
