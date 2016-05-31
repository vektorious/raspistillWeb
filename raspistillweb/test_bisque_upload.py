# Example script of how to upload an image file to Bisque, performing login
# through CAS.

#from bqapi.bqclass import fromXml
from bqapi.comm import BQSession, BQCommError
from bqapi.util import save_blob, save_image_pixels
from lxml import etree
import argparse

#MY_USER = 'prian_imt'
#MY_PASSWD = 'PRIAn@iPlant14'
#BISQUE_ROOT_URL = 'http://bovary.iplantcollaborative.org'
#MODULE_EXEC_URL = 'http://bovary.iplantcollaborative.org/module_service/MyData/execute'
LOCAL_FILE_PATH = 'pictures/IMG_2014-10-01_18-55-17.png'


def main():
    parser = argparse.ArgumentParser(description='Set Basic auth credentials on CAS protected Bisque')
    parser.add_argument ('-u', '--credentials', default=None, help="CAS credentials in form of user:password")
    parser.add_argument ("bisque_host", nargs=1)
    args = parser.parse_args()
    session = setbasicauth(args.bisque_host[0], *args.credentials.split(':'))
    
    resource = etree.Element('image', name="IMG_2014-10-01_18-55-17.png")
    etree.SubElement(resource, 'tag', name="experiment", value="RPi test")
    etree.SubElement(resource, 'tag', name="timestamp", value="2014-10-01_18-55-17")
    
    r = save_blob(session, LOCAL_FILE_PATH, resource=resource)
    #r = save_image_pixels(session, LOCAL_FILE_PATH)
    if r is None:
        print("Error uploading")
    else:
        uri = r.get('uri')
        print(uri)


def setbasicauth(bisquehost, username, password):
    s = BQSession()
    print(username, password, bisquehost)
    s.init_cas(username, password, bisque_root=bisquehost, create_mex=False)
    r = s.c.post(bisquehost + "/auth_service/setbasicauth", data = { 'username': username, 'passwd': password})
    #print r.text
    return s


if __name__ == "__main__":
    main()
