#!/usr/bin/env python

import os
import sys
import json
import logging

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.export

import mapzen.whosonfirst.hierarchy
import mapzen.whosonfirst.spatial.postgres
import mapzen.whosonfirst.properties

class importer:

    def __init__(self, **kwargs):

        self.retired = retired(**kwargs)
        self.existing = existing(**kwargs)
        self.fresh = fresh(**kwargs)

        self.relations = [
            "ancestors",
            "peers",
            "descendants"
        ]

    def process (self):

        updated = []

        self.retired.process()

        # experimental - trying to see whether we can just add localities
        # to the standard relations in class existing/fresh ...
        # self.locality.process()

        # this is freakishly experimental - it's also not proven
        # basically there are instances when an import will fail but not
        # before _new_ features have been indexed in PGIS; the consequence
        # of this is that when looking up descendants for a given feature
        # we might return things that are part of the import but that have
        # not been written to disk yet (because we will have rolled-back
        # the update to address whatever caused the import to fail).
        #
        # to be perfectly honest I hate the idea of 'pre_export' -ing things
        # so the moment that we can prune PGIS with a filelist (derived from
        # the records contained in an update) then it will probably be
        # removed: https://github.com/whosonfirst/go-whosonfirst-pgis/issues/6
        #
        # for now we're just going to see if it works at all...
        # (20170801/thisisaaronland)

        # see also: https://github.com/whosonfirst-data/whosonfirst-data/issues/870

        pre_export = False

        if pre_export:
            for rel in self.relations:
                self.fresh.pre_export(rel)

        for rel in self.relations:

            updated = self._update(updated, self.existing.process(rel))
            updated = self._update(updated, self.fresh.process(rel))

        return updated

    def _update(self, current, new):

        for u in new:
            if not u in current:
                current.append(u)

        return current

class base:

    def __init__(self, **kwargs):

        include = []
        exclude = [ "venue" ]

        self.include = include
        self.exclude = exclude

        self.data_root = kwargs["data_root"]
        self.debug = kwargs["debug"]

        root = os.path.join(kwargs["data_root"], kwargs["repo"])
        self.data = os.path.join(root, "data")
        
        self.exporter = mapzen.whosonfirst.export.flatfile(self.data)
        
        pg_args = {
            "dbname": kwargs["pgis_database"],
            "username": kwargs["pgis_username"],
            "password": kwargs["pgis_password"],
            "host": kwargs["pgis_host"],
        }
        
        self.pg_client = mapzen.whosonfirst.spatial.postgres.postgis(**pg_args)
        self.ancs = mapzen.whosonfirst.hierarchy.ancestors(spatial_client=self.pg_client)

        self.aliases = mapzen.whosonfirst.properties.aliases()
        self.updates = kwargs["updates"]

    def is_alt_file(self, path):

        if path.endswith("_alt.geojson"):
            return True

        if path.endswith("_alt_points.geojson"):
            return True

        return False

    def process(self):
        raise Exception, "Please subclass me"

    # because this: https://github.com/whosonfirst-data/whosonfirst-data/issues/673#issuecomment-282795658

    def process_mz_geom_id(self, update_wofid, new_geom, new_src):

        update_feature = mapzen.whosonfirst.utils.load(self.data, update_wofid)
        update_feature = self.produce_alt_geom(update_feature)				# see the way we're refreshing the feature object?
            
        update_feature["geometry"] = new_geom
        update_feature["properties"]["src:geom"] = new_src
            
        if self.debug:
            logging.info("update geometry to use %s" % new_src)
        else:
            self.exporter.export_feature(update_feature)

    # as in a new alt geom that we're just adding to the dataset

    def import_alt_geom(self, alt_feature):

        alt_props = alt_feature["properties"]
        wofid = alt_props.get("id", None)

        if wofid == None:
            logging.error("alt geom is missing a WOF ID")
            return False

        prepped = self.aliases.prep(alt_props)

        """
        from stepps00 (20170814): 

        that works.. I've created alt geometries that only include wof:id, src:geom, and the geom/geometry props
        for future alt files Ill remove props that arent in the `allowed` props
        """

        allowed = (
            "wof:id", "wof:placetype", "wof:repo",
            "lbl:latitude", "lbl:longitude",
            "reversegeo:latitude", "reversegeo:longitude",
            "src:geom",
        )

        for k, v in prepped.items():

            if not k in allowed:
                del(prepped[k])

        alt_src = prepped["src:geom"]

        feature = mapzen.whosonfirst.utils.load(self.data, wofid)
        props = feature["properties"]

        alt = props.get("src:geom_alt", [])

        if not alt_src in alt:
            alt.append(alt_src)

            props["src:geom_alt"] = alt
            feature["properties"] = props

            if self.debug:
                logging.info("existing props for %s would be %s" % (wofid, props))
            else:
                self.exporter.export_feature(feature)

        alt_feature["properties"] = prepped

        if self.debug:
            logging.info("alt props for %s would be %s" % (wofid, prepped))
        else:
            self.exporter.export_alt_feature(alt_feature, alt=True, source=alt_src)

    # this is a bad name - the longer version would be _make_current_geom_an_alt_geom
    # or something like that... (20170227/thisisaaronland)

    def produce_alt_geom(self, feature):

        props = feature["properties"]
        wofid = props["wof:id"]

        old_geom = feature["geometry"]
        old_src = props.get("src:geom", "unknown")
        
        alt_props = {
            "wof:id": props["wof:id"],
            "wof:placetype": props["wof:placetype"],
            "src:geom": old_src,
        }
        
        alt_feature = {
            "type": "Feature",
            "geometry": old_geom,
            "properties": alt_props
        }

        alt_src = alt_props["src:geom"]
        
        if self.debug:
            logging.info("alt props for %s would be %s" % (wofid, alt_props))
        else:
            self.exporter.export_alt_feature(alt_feature, alt=True, source=alt_src)

        alt = props.get("src:geom_alt", [])
                
        if not alt_src in alt:
            alt.append(alt_src)
                    
        props["src:geom_alt"] = alt
        feature["properties"] = props

        if self.debug:
            logging.info("existing props for %s would be %s" % (wofid, props))
        else:
            self.exporter.export_feature(feature)

        return mapzen.whosonfirst.utils.load(self.data, props["wof:id"])

class fresh(base):

    def __init__(self, **kwargs):

        base.__init__(self, **kwargs)

        self.possible = {

            'ancestors': [
                'no_wof_localadmin.geojson',
                'no_wof_localadmin_alt.geojson',
                'no_wof_boroughs.geojson',
                'no_wof_locality.geojson',
                'no_wof_boroughs_points.geojson',
                'no_wof_macrohoods.geojson',
                'no_wof_macrohoods_points.geojson',
                'no_wof_neighbourhoods.geojson',
                'no_wof_water_macro.geojson',
                'no_wof_water_macro_points.geojson',
            ],
            'peers': [
                'no_wof_neighbourhoods.geojson',
                'no_wof_neighbourhoods_points.geojson',
                'no_wof_waterways.geojson',
                'no_wof_waterways_points.geojson',
            ],
            'descendants': [
                'no_wof_microhoods.geojson',
                'no_wof_microhoods_points.geojson',
                'no_wof_campus.geojson',
                'no_wof_water_micro.geojson',
                'no_wof_water_micro_points.geojson',
                
                # please implement me (20170814/thisisaaronland)
                # 'no_wof_water_micro_alt.geojson',
                # 'no_wof_water_micro_alt_points.geojson'
            ]
        }

    # experimental - see notes above in the 'fresh' process method

    def pre_export(self, relation):

        logging.info("[pre_export][fresh] '%s'" % relation)

        if not self.possible.get(relation, None):
            raise Exception, "unknown relation"

        possible = self.possible[relation]

        for fname in possible:

            path = os.path.join(updates, fname)

            if not os.path.exists(path):
                continue

            logging.info("[pre_export][fresh][%s] %s" % (relation, path))

            fh = open(path, "r")
            col = json.load(fh)
        
            for new_feature in col["features"]:
        
                new_props = new_feature["properties"]
                wofid = new_props.get("id", None)

                if wofid == None:
                    logging.error("[pre_export][fresh][%s] %s %s missing WOF ID" % (relation, fname))
                    raise Exception, "can not pre export"

                logging.debug("[pre_export][fresh][%s] %s %s new props are %s" % (relation, fname, wofid, new_props))

                prepped = self.aliases.prep(new_props)

                if prepped.get("mz:geom_id", None):

                    update_wofid = prepped.get("mz:geom_id")
                    self.process_mz_geom_id(update_wofid, new_feature["geometry"], prepped["src:geom"])

                    del(prepped["mz:geom_id"])

                # some feedback if we're debugging

                if self.debug:
                    logging.debug("[pre_export][fresh][%s] %s %s prepped props are %s" % (relation, fname, wofid, prepped))
                    continue
            
                new_feature["properties"] = prepped

                # save new properties to disk

                logging.debug("[pre_export][fresh][%s] %s %s export" % (relation, fname, wofid))

                self.exporter.export_feature(new_feature)

        return True

    def process(self, relation):

        logging.info("[process][fresh] '%s'" % relation)

        possible = self.possible.get(relation, [])
        updated = []

        for fname in possible:

            path = os.path.join(updates, fname)

            if not os.path.exists(path):
                continue

            is_alt = self.is_alt_file(path)

            logging.info("[process][fresh][%s] %s" % (relation, path))

            fh = open(path, "r")
            col = json.load(fh)
        
            for new_feature in col["features"]:
        
                new_props = new_feature["properties"]
                wofid = new_props.get("id", None)

                if is_alt:
                    logging.debug("[process][existing] import alt file for %s (%s)" % (wofid, path))
                    self.import_alt_geom(new_feature)
                    continue

                logging.debug("[process][fresh][%s] %s %s new props are %s" % (relation, fname, wofid, new_props))

                prepped = self.aliases.prep(new_props)

                if prepped.get("mz:geom_id", None):

                    update_wofid = prepped.get("mz:geom_id")
                    self.process_mz_geom_id(update_wofid, new_feature["geometry"], prepped["src:geom"])

                    del(prepped["mz:geom_id"])

                # some feedback if we're debugging

                if self.debug:
                    logging.debug("[process][fresh][%s] %s %s prepped props are %s" % (relation, fname, wofid, prepped))
                    continue
            
                new_feature["properties"] = prepped

                # save new properties to disk

                logging.debug("[process][fresh][%s] %s %s export" % (relation, fname, wofid))

                self.exporter.export_feature(new_feature)

                # now rebuild all the hierarchies

                rebuild_kwargs = {
                    "data_root": self.data_root,
                    "debug": self.debug,
                    "include": self.include,
                    "exclude": self.exclude
                }

                logging.debug("[process][fresh][%s] %s %s rebuild and export" % (relation, fname, wofid))

                for r in self.ancs.rebuild_and_export_feature(new_feature, **rebuild_kwargs):

                    if not r in updated:
                        updated.append(r)

        return updated

class existing(base):

    def __init__(self, **kwargs):

        base.__init__(self, **kwargs)

        self.possible = {
            'ancestors': [
                'wof_localadmin.geojson',
                'wof_localadmin_alt.geojson',
                'wof_boroughs.geojson',
                'wof_locality.geojson',	
                'wof_boroughs_points.geojson',
                'wof_macrohoods.geojson',
                'wof_macrohoods_points.geojson'
                'wof_neighbourhoods.geojson',
                'wof_water_macro.geojson'
                'wof_water_macro_points.geojson'
            ],
            'peers': [
                'wof_neighbourhoods.geojson',
                'wof_neighbourhoods_points.geojson',
                'wof_waterways.geojson',
                'wof_waterways_points.geojson',                
            ],
            'descendants': [
                'wof_microhoods.geojson',
                'wof_microhoods_points.geojson',
                'wof_campus.geojson',
                'wof_water_micro.geojson',
                'wof_water_micro_points.geojson',

                # please implement me (20170814/thisisaaronland)
                # 'wof_water_micro_alt.geojson',
                # 'wof_water_micro_alt_points.geojson'
            ]
        }

    def process(self, relation):

        logging.info("[process][existing] %s" % relation)

        possible = self.possible.get(relation, [])
        updated = []

        for fname in possible:

            path = os.path.join(self.updates, fname)

            if not os.path.exists(path):
                continue

            is_alt = self.is_alt_file(path)

            logging.info("[process][existing][%s] %s" % (relation, fname))

            fh = open(path, "r")
            col = json.load(fh)

            for new_feature in col["features"]:
        
                new_props = new_feature["properties"]
                wofid = new_props["id"]

                if is_alt:
                    logging.debug("[process][existing] import alt file for %s (%s)" % (wofid, path))
                    self.import_alt_geom(new_feature)
                    continue

                logging.debug("[process][existing][%s] %s %s new props are %s" % (relation, fname, wofid, new_props))

                existing_feature = mapzen.whosonfirst.utils.load(self.data, wofid)
                existing_feature = self.produce_alt_geom(existing_feature)

                prepped = self.aliases.prep(new_props)

                if self.debug:
                    logging.debug("[process][existing][%s] %s %s prepped props are %s" % (relation, fname, wofid, prepped))
                    continue            

                # does it make sense to do this here?
                # see notes above

                """
                if prepped.get("mz:geom_id", None):

                    update_wofid = prepped.get("mz:geom_id")
                    self.process_mz_geom_id(update_wofid, new_feature["geometry"], prepped["src:geom"])
                    del(prepped["mz:geom_id"])
                """

                for k, v in prepped.items():
                    existing_feature["properties"][k] = v

                logging.debug("[process][existing][%s] %s %s export" % (relation, fname, wofid))

                existing_feature["geometry"] = new_feature["geometry"]            
                self.exporter.export_feature(existing_feature)
            
                rebuild_kwargs = {
                    "data_root": self.data_root,
                    "debug": self.debug,
                    "include": self.include,
                    "exclude": self.exclude
                }

                logging.debug("[process][existing][%s] %s %s rebuild and export" % (relation, fname, wofid))

                for r in self.ancs.rebuild_and_export_feature(existing_feature, **rebuild_kwargs):        

                    if not r in updated:
                        updated.append(r)

            if relation == "locality":
                break

        return updated

class retired(base):

    def __init__(self, **kwargs):
        base.__init__(self, **kwargs)

        self.possible = {
            'retired': [
                'cessation.geojson',
                'cessation_points.geojson',
                'deprecated.geojson',
                'deprecated_points.geojson',
            ]
        }

    def process(self, relation='retired'):

        possible = self.possible.get(relation, [])

        for fname in possible:

            path = os.path.join(self.updates, fname)

            if not os.path.exists(path):
                continue

            logging.info("process %s" % path)

            fh = open(path, "r")
            col = json.load(fh)

            for feature in col["features"]:

                props = feature["properties"]
                wofid = props["id"]
                
                prepped = self.aliases.prep(props)
            
                if self.debug:

                    logging.info(prepped)
                    continue

                old_feature = mapzen.whosonfirst.utils.load(data, wofid)
                old_props = old_feature["properties"]

                for k, v in prepped.items():

                    if v == None:
                        continue

                    if v == "":
                        continue

                    old_props[k] = v

                old_feature["properties"] = old_props
                self.exporter.export_feature(old_feature)

                self.pg_client.index_feature(old_feature, data_root=self.data_root)

if __name__ == "__main__":

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-D', '--data-root', dest='data_root', action='store', default='/usr/local/data', help='... (Default is /usr/local/data)')
    opt_parser.add_option('-R', '--repo', dest='repo', action='store', default='whosonfirst-data', help='... (Default is whosonfirst-data)')

    opt_parser.add_option('-U', '--updates', dest='updates', action='store', default=None, help='Where your neighbourhood updates are located.')

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
        
    root = os.path.join(options.data_root, options.repo)
    data = os.path.join(root, "data")

    if not os.path.exists(data):
        logging.error("Invalid REPO/data directory %s" % data)
        sys.exit(1)

    updates = options.updates

    if updates == None:
        logging.error("Missing updates directory")
        sys.exit(1)

    updates = os.path.abspath(updates)

    if not os.path.exists(updates):
        logging.error("Invalid updates directory %s" % updates)
        sys.exit(1)

        pg_args = {
        }

    kwargs = {
        "data_root": options.data_root,
        "repo": options.repo,
        "updates": updates,
        "debug": options.debug,
        "pgis_database": options.pgis_database,
        "pgis_username": options.pgis_username,
        "pgis_password": options.pgis_password,
        "pgis_host": options.pgis_host,        
    }

    imp = importer(**kwargs)
    print imp.process()
