# tasks

## Important

This is wet paint. Talk to Aaron, first. Also, a bunch of these things will probably be renamed to have... you know, names that are more descriptive and make sense. It's early days still.

## neighbourhood-tool.py

Important things to note about this tool:

1. Descendant venues are _not_ processed by default. That's because there are a lot of them and the thinking (hope) is that they can be processed in a second pass allowing other PRs involving the `whosonfirst-data` (admin) repo to be processed at the same time. In order to process venues you will need to re-run the tool and pass in the `-V` (for venues) flag.

### Basic workflow

As of this writing none of this has been automated yet. That still needs to be done. In the meantime, the workflow for processing PRs break down in to four independent sets of tasks, that should be made queue-able and schedule-able.

#### Step 1

* create branch for issue
* fetch files for issue

#### Step 2

* process files for issue in debug mode

#### Step 3

* process files for issue for real
* commit branch (and other relevant branches or repos)

#### Step 4

* merge issue with staging-work / master
* build metafiles
* push to master

Let's imagine that we are processing `Chicago_20170323.zip` which was produced as part of [issue #385](https://github.com/whosonfirst-data/whosonfirst-data/issues/385). The first thing is to grab the files in question:

```
mkdir -p /usr/local/data/whosonfirst-work/issue-385
cd /usr/local/data/whosonfirst-work/issue-385
wget http://whosonfirst.mapzen.com.s3.amazonaws.com/misc/Issue%20385/Chicago_20170323.zip
unzip Chicago_20170323.zip
```

Next, make sure everything is up to date:

```
cd whosonfirst-data
git checkout whosonfirst-staging
git pull origin master
git push origin whosonfirst-staging
```

Now create a new branch and merge the changes:

```
git checkout -b issue-385
```

Run the neighbourhood tool in debug mode, by passing the `-d` flag, to trap any outstanding glitches in the data. This is typically properties or aliases that are missing from the files defined in https://github.com/whosonfirst/whosonfirst-properties/tree/master/aliases.

```
./neighbourhood-tool.py -R whosonfirst-data -U /usr/local/data/whosonfirst-work/issue-385/Chicago_20170323 -d
```

Run the tool for real:

```
./neighbourhood-tool.py -R whosonfirst-data -U /usr/local/data/whosonfirst-work/issue-385/Chicago_20170323
...

[u'whosonfirst-data']
```

See the way we're spitting out the affected repos to `STDOUT` ? We'll need to figure out how/where to pass that along to things invoking this tool.

### What's going on (under the hood) when we run the neighbourhood tool?

_Please write me._

### What now?

Now we commit all the changes, which is pretty straightforward for the admin data:

```
cd whosonfirst-data
git commit -m "update all the things per issue #385" .
git push origin issue-385
```

### Pushing to master

_If this looks basically like a carbon-copy of what we do in the pr-tool (below) that's because it is. We should see if there's a way to reconcile both operations._

As of this writing, once a PR has been pushed to its branch it generally goes to @stepps00 for review and final sanity checking. Once he gives something the thumbs up then the process is as follows:

```
cd whosonfirst-data
git checkout staging-work
git pull origin issue-385
git push origin staging-work
git checkout master
git pull origin staging-work
wof-build-metafiles
git commit -m "update metafiles" .
git push origin master
```

At which point the GitHub webhooks will trigger `updated` and push the changes to the S3, the Spelunker, etc.

A couple things to note here:

* `wof-build-metafiles` is https://github.com/whosonfirst/go-whosonfirst-meta/blob/master/cmd/wof-build-metafiles.go. It is a Go port of the original Python code for generating metafiles inside a repo. It has two distinct advantages: 1. It is much much faster and 2. It doesn't suffer from Python's expected install/dependency hell.

* @dphiffer is currently working making rebuilding meta files a first-class "pipeline" task. How and where that fits in with this workflow remains to be determined.

### Venues?

Venues are still a lot of work.

The really short version is that you simply invoke the pr-tool with the `-V` flag. This will cause the tool to skip all non-venue placetypes:

```
./neighbourhood-tool.py -R whosonfirst-data -U /usr/local/data/whosonfirst-work/issue-385/Chicago_20170323 -V
```

In the case of issue 385 you should expect to see that there are changes in the `whosonfirst-data-venue-us-il` repo:
 
```
[u'whosonfirst-data-venue-us-il']
```

As noted above, we will need to figure out a way to relay this information to automated tasks. Also note that changes to the relevant venue repos will need to be commited. By now (having sanity checked the admin data) it's probably safe to assume that the venues can simply be checked in to master as-is.

## pr-tool.py

There are two important things to note about this tool:

1. It assumes that we're processing descendants and updating hierarchies. It's very possible that we will need to write a separate `process-a-PR-sans-hierarchy-stuff` tool, but that hasn't happened yet.

2. Descendant venues are _not_ processed by default. That's because there are a lot of them and the thinking (hope) is that they can be processed in a second pass allowing other PRs involving the `whosonfirst-data` (admin) repo to be processed at the same time. In order to process venues you will need to re-run the tool and pass in the `-V` (for venues) flag.

### Basic workflow

As of this writing none of this has been automated yet. That still needs to be done. In the meantime, the workflow for processing PRs break down in to four independent sets of tasks, that should be made queue-able and schedule-able.

#### Step 1

* create branch for PR
* merge PR
* commit branch

#### Step 2

* process PR in debug mode

#### Step 3

* process PR for real
* commit branch (and other relevant branches or repos)

#### Step 4

* merge PR with staging-work / master
* build metafiles
* push to master

Okay, let's say we have this PR: https://github.com/whosonfirst-data/whosonfirst-data/pull/752

First, make sure everything is up to date:

```
cd whosonfirst-data
git checkout whosonfirst-staging
git pull origin master
git push origin whosonfirst-staging
```

Now create a new branch and merge the changes:

```
git checkout -b pr-752
git checkout -b stepps00/sf-updates origin/stepps00/sf-updates
git merge pr-752
git checkout pr-752
git merge --no-ff stepps00/sf-updates
git push origin pr-752
```

Push the changes so we have a commit hash to revert to if something goes pear-shaped.

If you just want to see what files will be updated run the pr-tool with the `-l` flag. Here's where it gets interesting... for some definition of "interesting".

### The list files in a PR GitHub API method

Wouldn't it be great if we could just do this:

```
./pr-tool.py -l -P 752
```

Where `-P` is the ID of the pull request and get back a list of all the files in the PR? Yeah, that would be awesome. Unfortunately the GitHub API caps the number of files returned by the API at... 300. I have no idea why.

See also: https://developer.github.com/v3/pulls/#list-pull-requests-files

### The list commits in a PR GitHub API method

In cases where there are more than 300 files (and honestly how is an automated task supposed to know that in advance?) there is also a list all the commit hashes in a PR which can be invoked with the `-C` flag, like this:

```
./pr-tool.py -l -P 752 -C
```

Internally what the code will do is loop over each hash and execute the following Git command building the final list of files:

```
git show --pretty-format: --name-only COMMIT_HASH
```

Of course, the list all	the commit hashes API method caps the number of commit hashes at 250. For the time being we're going to enjoy the (likely) fact that this is not a ceiling we will hit anytime soon. One day we will and then... we will have a sob and then figure out an alternative, I guess.

See also: https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request

### The list all the files between two commits methods

Is pretty much what it sounds like:

```
./pr-tool.py -l --start-commit e3eb648fbdb868ba2bde17ffc49e5e2c5c73d984 --stop-commit baf61a5f09b07fb0b39fbda29e2e0717e21e703b
```

Internally the code is issuing the following Git command:

```
git show --name-only START_COMMIT^^..STOP_COMMIT
```

The problem here is that even if those two commit ranges (which book-end a PR) only encompassed 8 (I think...) files when they were added to Git, by the time the PR is processed you end up getting a list of like 45K files. Which is not what we want.

### The list of all the files between two branches methods

This basically has the same problem as listing files between two commit ranges (because it's essentially the same operation under the hood).

```
./pr-tool.py -l -I stepps00/sf-updates
```

Internally the code is issuing the following Git command:

```
git diff --name-only SOURCE_BRANCH..IMPORT_BRANCH
```

_The default source or `-S` branch is "staging-work"._

### Processing a PR in debug (dryrun) mode:

This is done by passing in the `-d` flag which will cause the tool to process all the files but not actually commit / write any changes to the filesystem or ancillary databases.

```
./pr-tool.py -d -I stepps00/sf-updates
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/271/102080271.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/273/102080273.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/275/102080275.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/279/102080279.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/281/102080281.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/102/080/283/102080283.geojson exists locally
...
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/110/883/206/5/1108832065.geojson exists locally
DEBUG:root:checking that /usr/local/data/whosonfirst-data/data/110/895/444/3/1108954443.geojson exists locally
ERROR:root:/usr/local/data/whosonfirst-data/data/110/895/444/3/1108954443.geojson does not exist locally, did you merge the PR?
```

For example, when I ran that I was in the `master` branch where `1108954443.geojson` didn't exist yet. Other possible scenarios are things like a file missing a `wof:repo` a `wof:parent_id` property. Neither of those cases should happen going forward but they have happened in the past. The point is: Things in a PR might be wonky so we want to double check it first.

With that sorted out let's try running things in `dryrun` mode again:

```
./pr-tool.py -d -I stepps00/sf-updates
DEBUG:root:load /usr/local/data/whosonfirst-data/data/859/225/83/85922583.geojson
DEBUG:root:bucket count (raw) county : 78
DEBUG:root:bucket count (raw) locality : 1
DEBUG:root:bucket count (raw) neighbourhood : 3
DEBUG:root:bucket count (raw) microhood : 2
DEBUG:root:bucket count (allplaces) empire : 0
DEBUG:root:bucket count (allplaces) country : 0
DEBUG:root:bucket count (allplaces) marinearea : 0
DEBUG:root:bucket count (allplaces) timezone : 0
DEBUG:root:bucket count (allplaces) dependency : 0
DEBUG:root:bucket count (allplaces) disputed : 0
DEBUG:root:bucket count (allplaces) macroregion : 0
DEBUG:root:bucket count (allplaces) region : 0
DEBUG:root:bucket count (allplaces) macrocounty : 0
DEBUG:root:bucket count (allplaces) county : 78
DEBUG:root:bucket count (allplaces) localadmin : 0
DEBUG:root:bucket count (allplaces) locality : 1
DEBUG:root:bucket count (allplaces) postalcode : 0
DEBUG:root:bucket count (allplaces) borough : 0
DEBUG:root:bucket count (allplaces) campus : 0
DEBUG:root:bucket count (allplaces) macrohood : 0
DEBUG:root:bucket count (allplaces) neighbourhood : 3
DEBUG:root:bucket count (allplaces) microhood : 2
DEBUG:root:bucket count (allplaces) intersection : 0
DEBUG:root:bucket count (allplaces) address : 0
DEBUG:root:bucket count (allplaces) building : 0
DEBUG:root:bucket count (allplaces) venue : 0
DEBUG:root:no features for empire
DEBUG:root:no features for country
DEBUG:root:no features for marinearea
DEBUG:root:no features for timezone
DEBUG:root:no features for dependency
DEBUG:root:no features for disputed
DEBUG:root:no features for macroregion
DEBUG:root:no features for region
DEBUG:root:no features for macrocounty
INFO:root:process county
INFO:root:/usr/local/bin/wof-pgis-index -debug -mode files /usr/local/data/whosonfirst-data/data/102/080/271/102080271.geojson
2017/06/02 16:29:44 INSERT INTO whosonfirst (id, parent_id, placetype_id, is_superseded, is_deprecated, meta, geom_hash, lastmod, geom, centroid) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 102080271 85687331 102312313 0 0 {"wof:name":"Manatí","wof:country":"PR","wof:repo":"whosonfirst-data","wof:hierarchy":[{"continent_id":102191575,"country_id":85633793,"county_id":102080271,"dependency_id":85633729,"region_id":85687331}]} ec5876b85864a0c57930139635fecfa0 2017-06-02T16:29:44Z ST_GeomFromGeoJSON('...') ST_GeomFromGeoJSON('{"type":"Point","coordinates":[-66.483398,18.451926]}')
DEBUG:root:
DEBUG:root:[102080271][Manatí] rebuild and export w/ kwargs {'rebuild_descendants': True, 'data_root': '/usr/local/data', 'debug': True, 'exclude': ['venue'], 'include': [], 'rebuild_feature': True}
...
DEBUG:root:filter placetype_id=1108906905
DEBUG:root:SELECT id, parent_id, placetype_id, meta, ST_AsGeoJSON(geom), ST_AsGeoJSON(centroid) FROM whosonfirst WHERE (ST_Intersects(ST_GeomFromGeoJSON(%s), geom) OR ST_Intersects(ST_GeomFromGeoJSON(%s), centroid)) AND is_superseded=%s AND is_deprecated=%s AND placetype_id=%s LIMIT 5000 OFFSET 0
DEBUG:root:no features for intersection
DEBUG:root:no features for address
DEBUG:root:no features for building
DEBUG:root:no features for venue
[u'whosonfirst-data', u'whosonfirst-data-postalcode-us']
```

See the way we're spitting out the affected repos to `STDOUT` ? We'll need to figure out how/where to pass that along to things invoking this tool.

### What now?

Now we commit all the changes, which is pretty straightforward for the admin data:

```
cd whosonfirst-data
git commit -m "update all the things per PR #752" .
git push origin pr-752
```

What is less straightforward is how to account for other repos. Currently we just create a new branch and push that. It's not ideal but it works.

Generally non-admin and non-venue repos are things have don't have immediate descendants to be rebuilt so they can be processed and pushed to master as-is:

```
cd /usr/local/data/whosonfirst-data/whosonfirst-data-postalcode-us
git checkout -b pr-752
git commit -m "update all the things per whosonfirst-data PR #752" .
git push origin pr-752
```

### Pushing to master

_If this looks basically like a carbon-copy of what we do in the neighbourhood-tool (above) that's because it is. We should see if there's a way to reconcile both operations._

As of this writing, once a PR has been pushed to its branch it generally goes to @stepps00 for review and final sanity checking. Once he gives something the thumbs up then the process is as follows:

```
cd whosonfirst-data
git checkout staging-work
git pull origin pr-752
git push origin staging-work
git checkout master
git pull origin staging-work
wof-build-metafiles
git commit -m "update metafiles" .
git push origin master
```

At which point the GitHub webhooks will trigger `updated` and push the changes to the S3, the Spelunker, etc.

A couple things to note here:

* `wof-build-metafiles` is https://github.com/whosonfirst/go-whosonfirst-meta/blob/master/cmd/wof-build-metafiles.go. It is a Go port of the original Python code for generating metafiles inside a repo. It has two distinct advantages: 1. It is much much faster and 2. It doesn't suffer from Python's expected install/dependency hell.

* @dphiffer is currently working making rebuilding meta files a first-class "pipeline" task. How and where that fits in with this workflow remains to be determined.

### Venues?

Venues are still a lot of work.

The really short version is that you simply invoke the pr-tool with the `-V` flag. This will cause the tool to skip all non-venue placetypes:

```
./pr-tool.py -l -P 752 -V
```

In the case of PR 752 you should expect to see that there are changes in the `whosonfirst-data-venue-us-ca` repo:
 
```
[u'whosonfirst-data-venue-us-ca']
```

As noted above, we will need to figure out a way to relay this information to automated tasks. Also note that changes to the relevant venue repos will need to be commited. By now (having sanity checked the admin data) it's probably safe to assume that the venues can simply be checked in to master as-is.

# Gotchas and known-knowns

## OMGWTF merge conflicts

Sometimes, in the course of processing multiple PRs or imports by the time things end up getting merged back in to staging-work/master there are merge conflicts. Typically these involve `wof:lastmodified` dates but sometimes it's other properties too. Honestly, I haven't figured out why this happens possibly because I am so irritated that it happens at all that I haven't tried very hard.

The consequence of these conflicts is stuff like this: https://github.com/whosonfirst-data/whosonfirst-data/issues/814

In that case I thought I had actually fixed the problem (see below) but because of a stupid redeclaring-a-variable brainfart the fix was never actually applied. Mostly just as an FYI, here is the quick-and-dirty (so dirty...) way to blanket apply anything in `HEAD`. It is included as a reference and _not_ as a recommendation for how to approach (or automate) the larger problem. How we "pause" an in-flight import job in order to fix stupid things like this and then pick things up again remains to be determined... Good times.

```
#!/usr/bin/env python

import sys
import os

wtf = sys.argv[1]

for bad in open(wtf, "r").readlines():

    bad = bad.strip()
    tmp = "%s.tmp" % bad

    infh = open(bad, "r")

    # outfh = sys.stdout
    outfh = open(tmp, "w")

    skip = False

    for ln in infh.readlines():
        
        if ln.startswith("<<<<<<<"):
            continue

        if ln.startswith("======="):
            skip = True
            continue

        if ln.startswith(">>>>>>>"):
            skip = False
            continue

        if skip == True:
            continue

        outfh.write(ln)

    outfh.close()
    os.rename(tmp, bad)
```

## See also

* https://github.com/whosonfirst/py-mapzen-whosonfirst-properties
* https://github.com/whosonfirst/py-mapzen-whosonfirst-hierarchy
* https://github.com/whosonfirst/py-mapzen-whosonfirst-spatial
