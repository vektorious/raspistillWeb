# raspistillWeb - web interface for raspistill
# Copyright (C) 2013 Tim Jungnickel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
import exifread
import os
import shutil
import signal
from subprocess import call, Popen, PIPE
import thread
import tarfile
from time import gmtime, strftime, localtime, asctime, mktime, sleep
from stat import *
from datetime import *
import Image
#from bqapi.bqclass import fromXml
from bqapi.comm import BQSession, BQCommError
from bqapi.util import save_blob
from lxml import etree
from time import time
from socket import gethostname


# Modify these lines to change the directory where the pictures and thumbnails
# are stored. Make sure that the directories exist and the user who runs this
# program has write access to the directories.
RASPISTILL_DIRECTORY = 'raspistillweb/pictures/' # Example: /home/pi/pics/
THUMBNAIL_DIRECTORY = 'raspistillweb/thumbnails/' # Example: /home/pi/thumbs/
TIMELAPSE_DIRECTORY = 'raspistillweb/time-lapse/'

IMAGE_EFFECTS = [
    'none', 'negative', 'solarise', 'sketch', 'denoise', 'emboss', 'oilpaint', 
    'hatch', 'gpen', 'pastel', 'watercolour', 'film', 'blur', 'saturation', 
    'colourswap', 'washedout', 'posterise', 'colourpoint', 'colourbalance', 
    'cartoon'
    ]

EXPOSURE_MODES = [
    'auto', 'night', 'nightpreview', 'backlight', 'spotlight', 'sports',
    'snow', 'beach', 'verylong', 'fixedfps', 'antishake', 'fireworks'
    ]
    
AWB_MODES = [
    'off', 'auto', 'sun', 'cloud', 'shade', 'tungsten', 'fluorescent',
    'incandescent', 'flash', 'horizon'
    ]

ISO_OPTIONS = [
    'auto', '100', '150', '200', '250', '300', '400', '500', 
    '600', '700', '800'
    ]
    
IMAGE_RESOLUTIONS = [
    '800x600', '1024x768', '1280x720', '1920x1080', '2592x1944'
    ]

ENCODING_MODES = [
    'jpg', 'bmp', 'gif', 'png'
    ]
    
IMAGE_HEIGHT_ALERT = 'Please enter an image height between 0 and 1945.'
IMAGE_WIDTH_ALERT = 'Please enter an image width between 0 and 2592.'
IMAGE_EFFECT_ALERT = 'Please enter a valid image effect.'
EXPOSURE_MODE_ALERT = 'Please enter a valid exposure mode.'
ENCODING_MODE_ALERT = 'Please enter a valid encoding mode.'
AWB_MODE_ALERT = 'Please enter a valid AWB mode.'
ISO_OPTION_ALERT = 'Please enter a valid ISO option.'
IMAGE_ROTATION_ALERT = 'Please enter a valid image rotation option.'
BISQUE_USER_ALERT = 'Please enter a valid username for Bisque.'
BISQUE_PSWD_ALERT = 'Please enter a valid password for Bisque.'
BISQUE_ROOT_URL_ALERT = 'Please enter a valid Bisque root URL.'

THUMBNAIL_SIZE = 128, 128
THUMBNAIL_JPEG_QUALITY = 80

database = []
timelapse_database = []

timelapse = False
p_timelapse = None

preferences_fail_alert = []
preferences_success_alert = False

# image parameter commands
image_width = '1024'
image_height = '768'
image_effect = 'none'
exposure_mode = 'auto'
awb_mode = 'auto'
encoding_mode = 'jpg'
timelapse_interval = 5
timelapse_time = 20
image_ISO = 'auto'
image_rotation = '180'
bisque_enabled = 'No'
bisque_user = ''
bisque_pswd = ''
bisque_root_url = 'http://bisque.iplantcollaborative.org'
bisque_local_copy = 'Yes'

# not implemented yet
image_quality = '100'
image_sharpness = '0'
image_contrast = '0'
image_brightness = '50'
image_saturation = '0'


###############################################################################
################################### Views #####################################
###############################################################################


# View for the /settings site
@view_config(route_name='settings', renderer='settings.mako')
def settings_view(request):
    global preferences_fail_alert, preferences_success_alert
        
    preferences_fail_alert_temp = []    
    if preferences_fail_alert is not []:
        preferences_fail_alert_temp = preferences_fail_alert
        preferences_fail_alert = []
     
    preferences_success_alert_temp = False  
    if preferences_success_alert:
        preferences_success_alert_temp = True
        preferences_success_alert = False
    
    host_name = gethostname()
    
    return {'project' : 'raspistillWeb',
            'hostName' : host_name,
            'image_effect' : image_effect,
            'exposure_mode' : exposure_mode,
            'awb_mode' : awb_mode,
            'encoding_mode' : encoding_mode,
            'image_effects' : IMAGE_EFFECTS,
            'exposure_modes' : EXPOSURE_MODES,
            'awb_modes' : AWB_MODES,
            'image_width' : str(image_width),
            'image_height' : str(image_height),
            'image_iso' : image_ISO,
            'iso_options' :  ISO_OPTIONS, 
            'timelapse_interval' : timelapse_interval,
            'timelapse_time' : timelapse_time,
            'bisque_enabled' : bisque_enabled,
            'bisque_user' : bisque_user,
            'bisque_pswd' : bisque_pswd,
            'bisque_root_url' : bisque_root_url,
            'bisque_local_copy' : bisque_local_copy,
            'preferences_fail_alert' : preferences_fail_alert_temp,
            'preferences_success_alert' : preferences_success_alert_temp,
            'image_rotation' : image_rotation,
            'image_resolutions' : IMAGE_RESOLUTIONS,
            'encoding_modes' : ENCODING_MODES
            } 
            
# View for the /archive site
@view_config(route_name='archive', renderer='archive.mako')
def archive_view(request):
    return {'project' : 'raspistillWeb',
            'database' : database
            }
                    
# View for the / site
@view_config(route_name='home', renderer='home.mako')
def home_view(request):
    if database == []:
        return HTTPFound(location='/photo')
    elif timelapse:
        return {'project': 'raspistillWeb',
                'imagedata' : database[0],
                'timelapse' : timelapse,
                }
    elif (mktime(localtime()) - mktime(database[0]['timestamp'])) > 1800: 
        return HTTPFound(location='/photo') 
    else:
        return {'project': 'raspistillWeb',
                'imagedata' : database[0],
                'timelapse' : timelapse,
                }

# View for the /timelapse site        
@view_config(route_name='timelapse', renderer='timelapse.mako')
def timelapse_view(request):
    return {'project': 'raspistillWeb',
            'timelapse' : timelapse,
            'timelapseInterval' : timelapse_interval,
            'timelapseTime' : timelapse_time,
            'timelapseDatabase' : timelapse_database
            }

# View for the reboot
@view_config(route_name='reboot', renderer='shutdown.mako')
def reboot_view(request):
    os.system("sudo shutdown -r now")
    #os.system("sudo shutdown -k now")
    host_name = gethostname()
    return {'project': 'raspistillWeb',
            'hostName' : host_name,
            }

# View for the shutdown
@view_config(route_name='shutdown', renderer='shutdown.mako')
def shutdown_view(request):
    os.system("sudo shutdown -hP now")
    #os.system("sudo shutdown -k now")
    host_name = gethostname()
    return {'project': 'raspistillWeb',
            'hostName' : host_name,
            }
  
# View for the timelapse start - no site will be generated
@view_config(route_name='timelapse_start')
def timelapse_start_view(request):
    global timelapse
    timelapse = True
    basename = strftime("IMG_%Y-%m-%d_%H-%M-%S", localtime())
    thread.start_new_thread( take_timelapse, (basename, ) )
    return HTTPFound(location='/timelapse') 

# View for the timelapse stop - no site will be generated
@view_config(route_name='timelapse_stop')
def timelapse_stop_view(request):
    global timelapse, p_timelapse
    if p_timelapse.poll() is None:
        os.killpg(p_timelapse.pid, signal.SIGTERM)
    timelapse = False
    return HTTPFound(location='/timelapse') 


# View for the archive delete - no site will be generated
@view_config(route_name='timelapse_delete')
def timelapse_delete_view(request):
    global timelapse_database
    print 'Deleting time-lapse...'
    os.remove(TIMELAPSE_DIRECTORY + timelapse_database[int(request.params['id'])]['filename'] + '.tar.gz')
    shutil.rmtree(TIMELAPSE_DIRECTORY + timelapse_database[int(request.params['id'])]['filename'])
    timelapse_database.pop(int(request.params['id']))
    return HTTPFound(location='/timelapse')

# View to take a photo - no site will be generated
@view_config(route_name='photo')
def photo_view(request):
    global database
    if timelapse:
        return HTTPFound(location='/') 
    else:
        basename = strftime("IMG_%Y-%m-%d_%H-%M-%S", localtime())
        filename = basename + '.' + encoding_mode
        take_photo(filename)
        filedata = extract_filedata(os.stat(RASPISTILL_DIRECTORY + filename))
        #f = open(RASPISTILL_DIRECTORY + filename_jpg,'rb')
        #exif = extract_exif(exifread.process_file(f))
        imagedata = dict(filedata.items())
        imagedata['filename'] = filename
        imagedata['image_effect'] = image_effect
        imagedata['exposure_mode'] = exposure_mode
        imagedata['awb_mode'] = awb_mode
        imagedata['encoding_mode'] = encoding_mode
        im = Image.open(RASPISTILL_DIRECTORY + filename)
        width, height = im.size
        imagedata['resolution'] = str(width) + ' x ' + str(height)
        database.insert(0,imagedata)
        im.thumbnail(THUMBNAIL_SIZE, Image.ANTIALIAS)
        im.save(THUMBNAIL_DIRECTORY + basename + '.jpg', 'JPEG', quality=THUMBNAIL_JPEG_QUALITY, optimize=True, progressive=True)
        if bisque_enabled == "Yes" and bisque_local_copy == "No":
            print 'Deleting local copy of \'' + filename + '\''
            os.remove(RASPISTILL_DIRECTORY + filename)
        return HTTPFound(location='/')
         
# View for the archive delete - no site will be generated
@view_config(route_name='delete')
def delete_view(request):
    global database
    os.remove(RASPISTILL_DIRECTORY + '/' + database[int(request.params['id'])]['filename'])
    database.pop(int(request.params['id']))
    return HTTPFound(location='/archive')

# View for settings form data - no site will be generated      
@view_config(route_name='save')
def save_view(request):
    global exposure_mode, encoding_mode, image_effect, image_width, preferences_success_alert
    global image_height, preferences_fail_alert, awb_mode, image_ISO, image_rotation
    global timelapse_interval, timelapse_time
    global bisque_enabled, bisque_user, bisque_pswd, bisque_root_url, bisque_local_copy

    image_width_temp = request.params['imageWidth']
    image_height_temp = request.params['imageHeight']
    timelapse_interval_temp = request.params['timelapseInterval']
    timelapse_time_temp = request.params['timelapseTime']
    bisque_enabled_temp = request.params['bisqueEnabled']
    bisque_user_temp = request.params['bisqueUser']
    bisque_pswd_temp = request.params['bisquePswd']
    bisque_root_url_temp = request.params['bisqueRootUrl']
    bisque_local_copy_temp = request.params['bisqueLocalCopy']
    exposure_mode_temp = request.params['exposureMode']
    encoding_mode_temp = request.params['encodingMode']
    image_effect_temp = request.params['imageEffect']
    awb_mode_temp = request.params['awbMode']
    image_ISO_temp = request.params['isoOption']
    image_rotation_temp = request.params['imageRotation']
    image_resolution = request.params['imageResolution']
    
    if image_width_temp:
        if 0 < int(image_width_temp) < 2592:
            image_width = image_width_temp
        else:
            preferences_fail_alert.append(IMAGE_WIDTH_ALERT)
    
    if image_height_temp:
        if 0 < int(image_height_temp) < 1945:
            image_height = image_height_temp
        else:
            preferences_fail_alert.append(IMAGE_HEIGHT_ALERT)
            
    if not image_width_temp and not image_height_temp:
        image_width = image_resolution.split('x')[0]
        image_height = image_resolution.split('x')[1]
        
    if timelapse_interval_temp:
        timelapse_interval = int(timelapse_interval_temp)
        
    if timelapse_time_temp:
        timelapse_time = int(timelapse_time_temp)
    
    if bisque_enabled_temp:
        bisque_enabled = bisque_enabled_temp
        if bisque_enabled == "Yes":
            if bisque_user_temp:
                bisque_user = bisque_user_temp
            else:
                preferences_fail_alert.append(BISQUE_USER_ALERT)
            if bisque_pswd_temp:
                bisque_pswd = bisque_pswd_temp
            else:
                preferences_fail_alert.append(BISQUE_PSWD_ALERT)
            if bisque_root_url_temp:
                bisque_root_url = bisque_root_url_temp
            else:
                preferences_fail_alert.append(BISQUE_ROOT_URL_ALERT)
        if bisque_local_copy_temp and bisque_local_copy_temp in ['Yes','No']:
            bisque_local_copy = bisque_local_copy_temp
    
    if exposure_mode_temp and exposure_mode_temp in EXPOSURE_MODES:
        exposure_mode = exposure_mode_temp
    else:
        preferences_fail_alert.append(EXPOSURE_MODE_ALERT)

    if encoding_mode_temp and encoding_mode_temp in ENCODING_MODES:
        encoding_mode = encoding_mode_temp
    else:
        preferences_fail_alert.append(ENCODING_MODE_ALERT)
        
    if image_effect_temp and image_effect_temp in IMAGE_EFFECTS:
        image_effect = image_effect_temp
    else:
        preferences_fail_alert.append(IMAGE_EFFECT_ALERT)
        
    if awb_mode_temp and awb_mode_temp in AWB_MODES:
        awb_mode = awb_mode_temp
    else:
        preferences_fail_alert.append(AWB_MODE_ALERT)
        
    if image_ISO_temp and image_ISO_temp in ISO_OPTIONS:
        image_ISO = image_ISO_temp
    else:
        preferences_fail_alert.append(ISO_OPTION_ALERT)
        
    if image_rotation_temp and image_rotation_temp in ['0','90','180','270']:
        image_rotation = image_rotation_temp
    else:
        preferences_fail_alert.append(IMAGE_ROTATION_ALERT)  
        
    if preferences_fail_alert == []:
        preferences_success_alert = True 
            
    return HTTPFound(location='/settings')

###############################################################################
############ Helper functions to keep the code clean ##########################
###############################################################################

def take_photo(filename):
    if image_ISO == 'auto':
        iso_call = ''
    else:
        iso_call = ' -ISO ' + str(image_ISO)
    call(
        ['raspistill -t 500'
        + ' -n '
        + ' -w ' + str(image_width)
        + ' -h ' + str(image_height)
        + ' -e ' + encoding_mode
        + ' -ex ' + exposure_mode
        + ' -awb ' + awb_mode
        + ' -rot ' + str(image_rotation)
        + ' -ifx ' + image_effect
        + iso_call
        + ' -o ' + RASPISTILL_DIRECTORY + filename],
        stdout=PIPE, shell=True
        )
#    if not (RASPISTILL_DIRECTORY == 'raspistillweb/pictures/'):
#        call (
#            ['ln -s ' + RASPISTILL_DIRECTORY + filename
#            + ' ' + RASPISTILL_DIRECTORY + filename], shell=True
#            )
    if bisque_enabled == 'Yes':
        resource = etree.Element('image', name=filename)
        etree.SubElement(resource, 'tag', name="experiment", value="Phenotiki")
        etree.SubElement(resource, 'tag', name="timestamp", value=os.path.splitext(filename)[0])
        bqsession = setbasicauth(bisque_root_url, bisque_user, bisque_pswd)
        print 'Uploading \'' + filename + '\' to Bisque...'
        start_time = time()
        r = save_blob(bqsession, localfile=RASPISTILL_DIRECTORY+filename, resource=resource)
        elapsed_time = time() - start_time
        if r is None:
            print 'Error uploading!'
            preferences_fail_alert.append('Error uploading \'' + filename + '\' to Bisque!')
        else:
            print 'Image uploaded in %.2f seconds' % elapsed_time
            print r.items()
            print 'Image URI:', r.get('uri')
    
    return

def take_timelapse(filename):
    global timelapse, timelapse_database
    global p_timelapse, timelapse_interval, timelapse_time
    timelapsedata = {'filename' : filename}
    timelapsedata['timeStart'] = str(asctime(localtime()))
    os.makedirs(TIMELAPSE_DIRECTORY + filename)
    timelapse_interval_ms = timelapse_interval*1000
    timelapse_time_ms = timelapse_time*1000
    if image_ISO == 'auto':
        iso_call = ''
    else:
        iso_call = ' -ISO ' + str(image_ISO)
    try:
        print 'Starting time-lapse acquisition...'
        print ['raspistill -t 500'
            + ' -n '
            + ' -w ' + str(image_width)
            + ' -h ' + str(image_height)
            + ' -e ' + encoding_mode
            + ' -ex ' + exposure_mode
            + ' -awb ' + awb_mode
            + ' -rot ' + str(image_rotation)
            + ' -ifx ' + image_effect
            + iso_call
            + ' -tl ' + str(timelapse_interval_ms)
            + ' -t ' + str(timelapse_time_ms) 
            + ' -o ' + TIMELAPSE_DIRECTORY + filename + '/'
            + filename + '_%04d.' + encoding_mode]
        p_timelapse = Popen(
            ['raspistill -t 500'
            + ' -n '
            + ' -w ' + str(image_width)
            + ' -h ' + str(image_height)
            + ' -e ' + encoding_mode
            + ' -ex ' + exposure_mode
            + ' -awb ' + awb_mode
            + ' -rot ' + str(image_rotation)
            + ' -ifx ' + image_effect
            + iso_call
            + ' -tl ' + str(timelapse_interval_ms)
            + ' -t ' + str(timelapse_time_ms) 
            + ' -o ' + TIMELAPSE_DIRECTORY + filename + '/'
            + filename + '_%04d.' + encoding_mode],
            stdout=PIPE, shell=True, preexec_fn=os.setsid
            )
        p_timelapse.wait()
        print 'Done with time-lapse acquisition.'
    except:
        os.killpg(p_timelapse.pid, signal.SIGTERM)
        p_timelapse.wait()
        raise
    print 
    timelapsedata['n_images'] = str(len([name for name in os.listdir(TIMELAPSE_DIRECTORY + filename) if os.path.isfile(os.path.join(TIMELAPSE_DIRECTORY + filename, name))]))
    timelapsedata['resolution'] = str(image_width) + ' x ' + str(image_height)
    timelapsedata['image_effect'] = image_effect
    timelapsedata['exposure_mode'] = exposure_mode
    timelapsedata['encoding_mode'] = encoding_mode
    timelapsedata['awb_mode'] = awb_mode
    timelapsedata['timeEnd'] = str(asctime(localtime()))
    with tarfile.open(TIMELAPSE_DIRECTORY + filename + '.tar.gz', "w:gz") as tar:
        tar.add(TIMELAPSE_DIRECTORY + filename, arcname=os.path.basename(TIMELAPSE_DIRECTORY + filename))
    timelapse_database.insert(0,timelapsedata)
    timelapse = False
    return

def extract_exif(tags):
    print "ImageWidth = " + str(tags['Image ImageWidth'])
    return {
        'resolution' : str(tags['Image ImageWidth']) 
        + ' x ' + str(tags['Image ImageLength']),
        'ISO' : str(tags['EXIF ISOSpeedRatings']),
        'exposure_time' : str(tags['EXIF ExposureTime'])
            }

def extract_filedata(st):
    return {
        'date' : str(asctime(localtime(st.st_mtime))),
        'timestamp' : localtime(),
        'filesize': str(st.st_size/1000) + ' kB'
            }

def setbasicauth(bisquehost, username, password):
    bqsession = BQSession()
    bqsession.init_cas(username, password, bisque_root=bisquehost, create_mex=False)
    r = bqsession.c.post(bisquehost + "/auth_service/setbasicauth", data = { 'username': username, 'passwd': password})
    print r
    return bqsession

