#!/usr/bin/env python

import os
import sys
import logging

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.export

if __name__ == "__main__":

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-d', '--debug', dest='debug', action='store_true', default=False, help='...')
    opt_parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Be chatty (default is false)')

    options, args = opt_parser.parse_args()

    if options.debug:
        options.verbose = True

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    for repo in args:

        data = os.path.join(repo, "data")
        logging.info("checking %s" % data)

        exporter = mapzen.whosonfirst.export.flatfile(data)
        crawl = mapzen.whosonfirst.utils.crawl(data, inflate=True)

        for feature in crawl:

            props = feature["properties"]

            parentid = props.get("wof:parent_id", None)
            repo = props.get("wof:repo", None)

            updated = False

            if parentid == None:
                props["wof:parent_id"] = -1
                updated = True

            if repo == None:
                updated = True

            if not updated:
                continue

            logging.info("update %s (%s)" % (props["wof:id"], props["wof:name"]))

            if options.debug:
                continue

            feature["properties"] = props
            exporter.export_feature(feature)
