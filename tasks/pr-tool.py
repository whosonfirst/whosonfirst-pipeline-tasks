#!/usr/bin/env python

# THIS IS WORK IN PROGRESS - NO REFUNDS ACCEPTED (20161109/thisisaaronland)
# ./pr-tool.py -I stepps00/meso-admin1-1 -l > 660-list.txt

# /usr/local/data/whosonfirst-data/data/856/678/31/85667831.geojson because it is not current


import os
import sys
import logging
import pprint
import subprocess
import re

import requests
import json

import mapzen.whosonfirst.utils
import mapzen.whosonfirst.export
import mapzen.whosonfirst.placetypes
import mapzen.whosonfirst.uri

import mapzen.whosonfirst.hierarchy
import mapzen.whosonfirst.properties
import mapzen.whosonfirst.spatial.postgres

if __name__ == '__main__':

    # raise Exception, "Y R U DOING THIS"

    import optparse
    opt_parser = optparse.OptionParser()

    opt_parser.add_option('-D', '--data-root', dest='data_root', action='store', default='/usr/local/data', help='... (Default is /usr/local/data)')
    opt_parser.add_option('-R', '--repo', dest='repo', action='store', default='whosonfirst-data', help='... (Default is whosonfirst-data)')

    opt_parser.add_option('-P', '--pull-request', dest='pull_request', action='store', default=None, help='...')
    opt_parser.add_option('-C', '--pull-commits', dest='pull_commits', action='store_true', default=False, help='...')

    opt_parser.add_option('-X', '--ignore-commits', dest='ignore_commits', action='store', default=None, help='A comma-separated list of commit hashes to ignore, which is stupid but sometimes we have to deal with stupid things...')

    opt_parser.add_option('-F', '--filelist', dest='filelist', action='store', default=None, help='')

    opt_parser.add_option('-A', '--access_token', dest='access_token', action='store', default=None, help='...')

    opt_parser.add_option('--liberal', dest='liberal', action='store_true', default=False)
    opt_parser.add_option('--stats', dest='stats', action='store_true', default=False)

    opt_parser.add_option('--pgis-host', dest='pgis_host', action='store', default='localhost')
    opt_parser.add_option('--pgis-username', dest='pgis_username', action='store', default='postgres')
    opt_parser.add_option('--pgis-password', dest='pgis_password', action='store', default=None)
    opt_parser.add_option('--pgis-database', dest='pgis_database', action='store', default='whosonfirst')

    # this stuff is probably deprecated because it's kind of flakey... (20170602/thisisaaronland)

    opt_parser.add_option('-S', '--source-branch', action='store', default='staging-work', help='... (Defaults is staging-work)')
    opt_parser.add_option('-I', '--import-branch', action='store', default='', help='...')

    # this is more reliable assuming you're not passing -P (20170602/thisisaaronland)

    opt_parser.add_option('--start-commit', action='store', default=None, help='...')
    opt_parser.add_option('--stop-commit', action='store', default=None, help='...')

    opt_parser.add_option('-V', '--venues', action='store_true', default=False, help='... (Default is false)')

    opt_parser.add_option('-l', '--list', dest='list', action='store_true', default=False, help='List the files to be processed but don\'t do anything. (Default is false)')
    opt_parser.add_option('-d', '--debug', dest='debug', action='store_true', default=False, help='... (Default is false)')
    opt_parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Be chatty (Default is false)')

    options, args = opt_parser.parse_args()

    if options.debug:
        options.verbose = True

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        
    root = os.path.join(options.data_root, options.repo)
    data = os.path.join(root, "data")

    if not os.path.exists(data):
        logging.error("Invalid REPO/data directory %s" % data)
        sys.exit(1)

    include = []
    exclude = [ "postalcode", "venue" ]

    pg_args = {
        "dbname": options.pgis_database,
        "username": options.pgis_username,
        "password": options.pgis_password,
        "host": options.pgis_host,
    }

    pg_client = mapzen.whosonfirst.spatial.postgres.postgis(**pg_args)
    ancs = mapzen.whosonfirst.hierarchy.ancestors(spatial_client=pg_client)

    abs_repo = os.path.join(options.data_root, options.repo)
    repo_name = os.path.basename(abs_repo)

    pr_data = []
    pr_files = []
    pr_commits = []

    ignore_commits = []

    update_features = []

    """
    basically to side-step stuff like this which might happen if you merge a conflict manually
    as you're applying the PR... translation: no, we can't have nice things
    (20170906/thisisaaronland)
    
    ./tasks/pr-tool.py -C -P 619 -I 5b37f72ebcbe260c0ffce31967b573b05201b919
    INFO:root:git show --pretty=format: --name-only 5941e41a0a98dc9643d71c464db08d0b61312422
    INFO:root:git show --pretty=format: --name-only 03fac7a471f6136f43812e8687c21242fe460247
    INFO:root:git show --pretty=format: --name-only 9731c437c00e6c4352574b90fcc36e7a0beeb298
    INFO:root:git show --pretty=format: --name-only 5b37f72ebcbe260c0ffce31967b573b05201b919
    fatal: bad object 5b37f72ebcbe260c0ffce31967b573b05201b919
    WARNING:root:
    ERROR:root:Failed to get PR info for https://api.github.com/repos/whosonfirst-data/whosonfirst-data/pulls/619/commits, Command '['git', 'show', '--pretty=format:', '--name-only', u'5b37f72eb\
    cbe260c0ffce31967b573b05201b919']' returned non-zero exit status 128
    """

    if options.ignore_commits:
        ignore_commits = options.ignore_commits.split(",")

    # add skip_paths to options, because this:
    # https://github.com/whosonfirst-data/whosonfirst-data/pull/881#issuecomment-330650553
    
    skip_ids = []
    skip_paths = []

    for id in skip_ids:
        rel_path = mapzen.whosonfirst.uri.id2relpath(id)
        rel_path = os.path.join("data", rel_path)
        skip_paths.append(rel_path)

    # START OF PLEASE MOVE THIS IN TO A FUNCTION OR SOMETHING (OR AT LEAST NOT __main__)

    if options.filelist :

        abs_path = os.path.abspath(options.filelist)
        fh = open(abs_path, "r")

        for f in fh.readlines():

            f = f.strip()
            f = mapzen.whosonfirst.uri.id2relpath(f)
            f = os.path.join("data", f)

            if f in skip_paths:
                continue

            pr_files.append(f)

    else:

        # because we're likely going to need to invoke git below...

        os.chdir(abs_repo)
    
        # https://developer.github.com/v3/pulls/#list-pull-requests-files
        # Note: The response includes a maximum of 300 files... thanks, GitHub

        # https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request	<-- max 250 commits
        # https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository

        if options.pull_request:

            url = "https://api.github.com/repos/whosonfirst-data/%s/pulls/%s/files" % (repo_name, options.pull_request)

            if options.pull_commits:

                # because this:
                #
                # https://github.com/whosonfirst-data/whosonfirst-data/pull/654/files
                # https://github.com/whosonfirst-data/whosonfirst-data/pull/654/commits
                #
                # which should be 2,053 files
                #
                # but then this happens...
                #
                # ./pr-tool.py -l --start-commit 60b34fdad7e7aa5cbf1de2f32da44ccdcb180300 --stop-commit 027941faf103abefec769c17cbd1510be1dde101 | wc -l
                # 46917
                #
                # because... ????
                
                url = "https://api.github.com/repos/whosonfirst-data/%s/pulls/%s/commits" % (repo_name, options.pull_request)

                while url:

                    try:

                        headers = {}

                        if options.access_token:

                            auth = "Authorization: token %s" % options.access_token
                            headers["Authentication"] = auth

                        logging.debug("fetch %s" % url)
                        logging.debug(headers)

                        rsp = requests.get(url, headers=headers)

                        if rsp.status_code != 200:
                            raise Exception, rsp.content

                        pr_data = json.loads(rsp.content)

                        # gggggrrrrrrnnnnnhhhhhhhzzzzzpppphhhhffffftttttttt....
                        # see above

                        if options.pull_commits:

                            for details in pr_data:

                                sha = details['sha']

                                if sha in ignore_commits:
                                    logging.info("ignore commit hash %s" % sha)
                                else:

                                    cmd = [
                                        "git", "show",
                                        '--pretty=format:',
                                        "--name-only",
                                        sha
                                    ]
            
                                    logging.info(" ".join(cmd))

                                    try:
                                        raw = subprocess.check_output(cmd)
                                    except subprocess.CalledProcessError, e:
                                        logging.warning(e.output)
                                        raise Exception, e
                                    except Exception, e:
                                        raise Exception, e

                                    raw = raw.strip()

                                    for f in raw.splitlines():
                                
                                        f = f.strip();
                                        
                                        if f:

                                            if f in skip_paths:
                                                continue

                                            pr_files.append(f)

                        else:
                            for details in pr_data:
                                pr_files.append(details["filename"])

                        # WHY WHY WHY?????

                        link = rsp.headers.get('Link', None)

                        if link:

                            pat = re.compile(r'\<([^\>]+)>; rel="([^\)]+)"')

                            links = link.split(", ")
                            rels = {}

                            for l in links:

                                m = pat.match(l)

                                if m:
                        
                                    gr = map(str, m.groups())
                                    rels[gr[1]] = gr[0]
                            
                            next_url = rels.get("next", None)
                            logging.debug("next %s" % next_url)

                            if next_url == url:
                                break
                            else:
                                url = next_url

                        else:
                            break

                    except Exception, e:
            
                        logging.error("Failed to get PR info for %s, %s" % (url, e))
                        sys.exit(1)

                # end of while

            else:

                # because it is not uncommon for us to have PR or branches will thousands
                # of files in them... (20170413/thisisaaronland)

                os.chdir(abs_repo)

                """
                git diff --name-only e3eb648fbdb868ba2bde17ffc49e5e2c5c73d984..baf61a5f09b07fb0b39fbda29e2e0717e21e703b
                data/110/883/206/5/1108832065.geojson
                data/110/895/444/3/1108954443.geojson
                data/420/552/239/420552239.geojson
                data/420/782/041/420782041.geojson
                data/858/659/83/85865983.geojson
                data/859/225/83/85922583.geojson
                """

                # isn't this already in mz.wof.git ?

                cmd = [
                    "git", "diff",
                    "--name-only",
                    "%s..%s" % (options.source_branch, options.import_branch)
                ]

                # question: is there a way to derive all the commit hashes (we only care about the
                # bookends though) for a given branch or PR number?
                
                if options.start_commit and options.stop_commit:

                    cmd = [
                        "git", "show",
                        "--name-only",
                        "%s^^..%s" % (options.start_commit, options.stop_commit)
                    ]
            
                    try:
                        raw = subprocess.check_output(cmd)
                    except CalledProcessError, e:
                        logging.warning(CalledProcessError.output)
                        raise Exception, e
                    except Exception, e:
                        raise Exception, e
                        
                    raw = raw.strip()

                    pr_files = []

                    for f in raw.splitlines():
                        
                        if f in skip_paths:
                            continue
                            
                        pr_files.append(f)

                    if len(pr_files) == 0:
                        logging.info("Nothing to update!")
                        sys.exit(1)

    # END OF PLEASE MOVE ... (OR AT LEAST NOT __main__)
    
    if options.list:

        for rel_path in pr_files:
            print rel_path

        sys.exit(0)

    # first make sure we have all the files in the PR

    tmp = []

    for rel_path in pr_files:

        abs_path = os.path.join(abs_repo, rel_path)

        if not mapzen.whosonfirst.uri.is_wof_file(abs_path):
            continue

        logging.debug("checking that %s exists locally" % abs_path)

        if mapzen.whosonfirst.uri.is_alt_file(abs_path):
            continue

        if not os.path.exists(abs_path):

            if options.liberal:
                logging.warning("%s does not exist locally, did you merge the PR? also running w/ liberal options so whatEVAR..." % abs_path)
                continue
            else:
                logging.error("%s does not exist locally, did you merge the PR?" % abs_path)
                sys.exit(1)

        tmp.append(rel_path)

    pr_files = tmp

    # Second, filter out only the things we care about - note that we include things that
    # are "not current" in order so that we can rebuild the descendants (but not the feature
    # itself) below.

    for rel_path in pr_files:

        abs_path = os.path.join(abs_repo, rel_path)

        if not mapzen.whosonfirst.uri.is_wof_file(abs_path):
            continue

        if mapzen.whosonfirst.uri.is_alt_file(abs_path):
            logging.debug("skipping %s because it is an alt file" % abs_path)
            continue

        logging.debug("load %s" % abs_path)

        feature = mapzen.whosonfirst.utils.load_file(abs_path)
        props = feature["properties"]
        geom = feature["geometry"]

        # see what's going on here? we're only going to store pointers to the relevant
        # information we need to sort and filter things before we start processing them
        # that's because in certain too-too-large PRs (think whosonfirst-data 824) storing
        # an array of all 900K or so features causes the baby unix to cry.... good times
        # (20171025/thisisaaronland)

        update_features.append({
            "path": abs_path,
            "placetype": props["wof:placetype"],
            "type": geom["type"],
        })

        # update_features.append(feature)


    # Check that we have something to work with

    if len(update_features) == 0:
        logging.info("Nothing to update")
        sys.exit(0)

    # Sort all the files by placetype

    allplaces = []

    pt = mapzen.whosonfirst.placetypes.placetype("continent")

    for p in pt.descendents([ "common", "common_optional", "optional" ]):
        allplaces.append(str(p))

    #

    buckets = {}

    for feature_ref in update_features:

        # props = feature["properties"]
        # pt = props["wof:placetype"]

        pt = feature_ref["placetype"]
        f = buckets.get(pt, [])

        f.append(feature_ref)
        buckets[pt] = f


    if options.stats:

        for pt, features in buckets.items():
            print "%s %s" % (pt, len(features))

            types = {}

            for f in features:
                t = f["type"]
                count = types.get(t, 0)
                types[t] = count + 1
                
            for t, count in types.items():
                print "\t%s %s" % (t, count)

        sys.exit(0)

    updated = []

    include = []
    exclude = [ "postalcode", "venue" ]

    if options.venues:
        include = [ "venue" ]
        exclude = []

    for pt in buckets:
        logging.debug("bucket count (raw) %s : %s" % (pt, len(buckets.get(pt, []))))

    for pt in allplaces:
        logging.debug("bucket count (allplaces) %s : %s" % (pt, len(buckets.get(pt, []))))

    for pt in allplaces:

        features = buckets.get(pt, None)
        
        if not features:
            logging.debug("no features for %s" % pt)
            continue

        logging.info("process %s" % pt)

        for feature_ref in features:

            feature = mapzen.whosonfirst.utils.load_file(feature_ref["path"])
            geom = feature["geometry"]

            pg_client.index_feature(feature, data_root=options.data_root, debug=options.debug)

            rebuild_feature = True
            rebuild_descendants = True

            if geom["type"] == "Point":
                rebuild_descendants = False

            if not mapzen.whosonfirst.properties.is_current(feature):
                rebuild_feature = False

            rebuild_kwargs = {
                "rebuild_feature": rebuild_feature,
                "rebuild_descendants": rebuild_descendants,
                "data_root": options.data_root,
                "debug": options.debug,
                "include": include,
                "exclude": exclude,
            }

            for updated_repo in ancs.rebuild_and_export(feature, **rebuild_kwargs):

                if not updated_repo in updated:
                    updated.append(updated_repo)

    # PLEASE DO SOMETHING WITH updated HERE...                    
        
    print updated	
    sys.exit()
