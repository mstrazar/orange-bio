##!interval=7
##!contact=blaz.zupan@fri.uni-lj.si

from Orange.bio import obiTaxonomy, obiGEO
import cPickle
import re
import ftplib
import time
from datetime import datetime

from common import *

DOMAIN = "GEO"
GDS_INFO = "gds_info.pickled"
TITLE = "Gene Expression Omnibus data sets information"
TAGS = ["Gene Expression Omnibus", "data sets", "GEO", "GDS"]

FTP_NCBI = "ftp.ncbi.nih.gov"
NCBI_DIR = "pub/geo/DATA/SOFT/GDS"

force_update = False
# check if the DOMAIN/files are already on the server, else, create
if DOMAIN not in sf_server.listdomains():
    # DOMAIN does not exist on the server, create it
    sf_server.create_domain(DOMAIN)

localfile = sf_local.localpath(DOMAIN, GDS_INFO)

def _create_path_for_file(target): #KEGG uses this!
    try:
        os.makedirs(os.path.dirname(target))
    except OSError:
        pass

path = sf_local.localpath(DOMAIN)
if GDS_INFO in sf_server.listfiles(DOMAIN):
    print "Updating info file from server ..."
    sf_local.update(DOMAIN, GDS_INFO)
    info = sf_local.info(DOMAIN, GDS_INFO)
    gds_info_datetime = datetime.strptime(info["datetime"], "%Y-%m-%d %H:%M:%S.%f")
    
else:
    print "Creating a local path..."
    _create_path_for_file(localfile)
    f = file(localfile, "wb")
    cPickle.dump(({}, {}), f, True)
    f.close()
    sf_server.upload(DOMAIN, GDS_INFO, localfile, TITLE, TAGS)
    sf_server.protect(DOMAIN, GDS_INFO, "0")
    gds_info_datetime = datetime.fromtimestamp(0)
    


# read the information from the local file
gds_info, excluded = cPickle.load(file(localfile, "rb"))
# excluded should be a dictionary (GEO_ID, TAX_ID)

# if need to refresh the data base
if force_update:
    gds_info, excluded = ({}, {})

# list of common organisms may have changed, rescan excluded list
excluded = dict([(id, taxid) for id, taxid in excluded.items() 
                 if taxid not in obiTaxonomy.common_taxids()])
excluded.update([(id, info["taxid"]) for id, info in gds_info.items() 
                 if info["taxid"] not in obiTaxonomy.common_taxids()])
gds_info = dict([(id, info) for id, info in gds_info.items() 
                 if info["taxid"] in obiTaxonomy.common_taxids()])

# get the list of GDS files from NCBI directory

print "Retrieving ftp directory ..."
ftp = ftplib.FTP(FTP_NCBI)
ftp.login()
ftp.cwd(NCBI_DIR)
dirlist = []
ftp.dir(dirlist.append)

from datetime import timedelta
from datetime import datetime
def modified(line):
    line = line.split()
    try:
        date  = " ".join(line[5: 8] + [str(datetime.today().year)])
        df = datetime.strptime(date, "%b %d %H:%M %Y")
        if df > datetime.today(): #this date means previous year
            df = df - timedelta(365)
        return df
    except ValueError:
        pass
    try:
        date = " ".join(line[5: 8])
        return datetime.strptime(date, "%b %d %Y")
    except ValueError:
        print "Warning: could not retrieve modified date for\n%s" % line
    return datetime.today()
    
m = re.compile("GDS[0-9]*")
gds_names = [(m.search(d).group(0), modified(d)) for d in dirlist if m.search(d)]
#gds_names = [name for name, time_m in gds_names if time_t > gds_info_datetime]
#gds_names = [m.search(d).group(0) for d in dirlist if m.search(d)]
#gds_names = [name for name in gds_names if not(name in gds_info or name in excluded)]
avail_names = [ n for n,_ in gds_names ]
gds_names = [name for name, time_m in gds_names if not(name in gds_info or name in excluded) or time_m > gds_info_datetime]
skipped = []
deleted = set(gds_info.keys()) - set(avail_names)

if len(gds_names) or len(deleted):
    print "delete", deleted

    for d in deleted:
        del gds_info[d]

    for count, gds_name in enumerate(gds_names):
        print "%3d of %3d -- Adding %s ..." % (count+1, len(gds_names), gds_name)
        try:
            time.sleep(1)
            gds = obiGEO.GDS(gds_name)
            if gds.info["taxid"] not in obiTaxonomy.common_taxids():
                excluded[gds_name] = gds.info["taxid"]
                print "... excluded (%s)." % gds.info["sample_organism"]
            else:
                gds_info.update({gds_name: gds.info})
                f = file(localfile, "wb")
                cPickle.dump((gds_info, excluded), f, True)
                f.close()
                print "... added."
        except Exception, ex:
            print "... skipped (error):", str(ex)
            skipped.append(gds_name)
    
print "Updating %s:%s on the server ..." % (DOMAIN, GDS_INFO)
 
sf_server.upload(DOMAIN, GDS_INFO, localfile, TITLE, TAGS)
sf_server.protect(DOMAIN, GDS_INFO, "0")

print
print "GDS data sets: %d" % len(gds_info)
print "Organisms:"
organisms = [info["sample_organism"] for info in gds_info.values()]
for org in set(organisms):
    print "  %s (%d)" % (org, organisms.count(org))
