#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import requests
import logging
import socket
import os

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


'''
Interaction with the EOSC service catalogue.
The base url is currently:

Merret Buurman, DKRZ, 2022-04-12
'''

# expires in 12 months, according to https://aai.eosc-portal.eu/providers-api/refreshtoken.php
EOSC_REFRESH_URL = 'https://api.eosc-portal.eu'
EOSC_REFRESH_URL = 'https://aai.eosc-portal.eu/oidc/token'
# expires in 1 hour, according to https://aai.eosc-portal.eu/providers-api/refreshtoken.php
EOSC_ACCESS_TOKEN = None


def validate_service_metadata(md, validation_url, add_dummy_id=False):
    LOGGER.debug('Validating metadata at EOSC, at %s...' % validation_url)

    # Initially, the data has no id, but validation needs one.
    if not 'id' in md and add_dummy_id:
        md['id'] = 'blablabla_dummy_fake'

    try:
        timeout = 5
        resp = requests.post(validation_url, json=md, timeout=timeout,
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'})
    except (socket.timeout, requests.exceptions.ReadTimeout) as e:
        LOGGER.error('NOT OK: Validating metadata at EOSC... failed.')
        LOGGER.warning('Ran into timeout during validation (%s seconds)' % timeout)
        return

    if resp.status_code == 200:
        LOGGER.info('OK: Validating metadata at EOSC... passed.')
    elif resp.status_code == 409:
        LOGGER.warning('NOT OK: Validating metadata at EOSC... not passed.')
        LOGGER.debug('Status code: %s' % resp.status_code)
        LOGGER.debug('Content: %s' % resp.content)
        errorlong = resp.json()['error']
        #error, field = errorlong.split(' Found in field ')
        #field = field.strip("'")
        LOGGER.warning('________Error, field:_______\n\n%s\n' % (errorlong))      
    else:
        LOGGER.error('NOT OK: Validating metadata at EOSC... failed.')
        LOGGER.error('Status code: %s' % resp.status_code)
        LOGGER.error('Content: %s' % resp.content)

        if resp.status_code == 400 and len(resp.content.strip()) == 0:
            # This seems to be an error on the EOSC server side.
            # Missing http is known to cause this, but other problems may cause the same bug.
            LOGGER.error('This MIGHT indicate a missing "http://" or "https://" in front of an URL, such as field "useCases", "webpage" or "multimedia".')  
            LOGGER.error('This MIGHT indicate that a field that should have string value, has an empty list, e.g. "paymentModel"')  


def get_new_access_token():
    # Only used inside this module.

    '''
    curl -X POST 'https://aai.eosc-portal.eu/oidc/token' -d 'grant_type=refresh_token&refresh_token=eyJhbGciOiJub25lIn0.eyJleHAiOjE2ODA3ODYyMjgsImp0aSI6ImQ1NmQ5ZmUxLTgwZDItNDkyOS05MGYyLTdiMzA3ZTFhZDZlMiJ9.&client_id=2373c5f0-c4bd-4918-aea3-f8bac3819f49&scope=openid%20email%20profile' | python -m json.tool;
    '''


    LOGGER.debug('Requesting a new access token from EOSC...')
    eosc_client_id = os.environ.get('EOSC_CLIENT_ID')
    eosc_refresh_token = os.environ.get('EOSC_REFRESH_TOKEN')
    data = {'grant_type':'refresh_token', 'refresh_token': eosc_refresh_token,
            'client_id': eosc_client_id, 'scope': 'openid email profile'}
    #data = {'grant_type':'refresh_token', 'refresh_token': eosc_refresh_token}
    resp = requests.post(EOSC_REFRESH_URL, data=data)
    if resp.status_code == 200:
        new_access_token = resp.json()['access_token']
        LOGGER.debug('Got a new access token from EOSC.')
        global EOSC_ACCESS_TOKEN
        EOSC_ACCESS_TOKEN = new_access_token

        # FOR COMPARISON:
        import hashlib
        md5 = hashlib.md5(new_access_token.encode('utf-8')).hexdigest()
        LOGGER.debug('Got a new access token with md5sum %s' % md5)
        LOGGER.debug('Token: %s' % new_access_token)
        import datetime
        LOGGER.debug('Time:  %s' % datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))
        LOGGER.debug("Test md5sum on command line: printf '%s' \"TOKEN\" | md5sum")

        return new_access_token

        # Apparenlty it is valid 12 months, so I will not go through the hassle to write a storage for the refresh token...
        #new_refresh_token = resp.json()['refresh_token']
        #return new_access_token, new_refresh_token
    else:
        err_msg = 'Could not get new token (http %s): %s' % (resp.status_code, resp.content)
        LOGGER.error(err_msg)
        raise RuntimeError(err_msg)
        # When I use this:
        # {'grant_type':'refresh_token', 'refresh_token': eosc_refresh_token}
        # I run into:
        # RuntimeError: Could not get new token (http 401): b'{"error":"invalid_client","error_description":"Bad client credentials"}'



    '''
    Response:
    {
        "access_token": "eyJraWQiOi...Acyw-S69M8...iw",
        "expires_in": 3599,
        "id_token": "eyJraWQiOiJv...H7zGMSg",
        "refresh_token": "eyJhbGc...ub25lIn...",
        "scope": "openid profile email",
        "token_type": "Bearer"
    }
    '''


def make_authorized_request(url, http_verb, headers, data):
    # Only used inside this module.
    LOGGER.debug('Making authorized request to EOSC...')

    if EOSC_ACCESS_TOKEN is None:
        LOGGER.debug('Will ask for an access token.')
        get_new_access_token()

    # TRY:
    #consumer_key_secret_enc = base64.b64encode(consumer_key_secret.encode()).decode()

    auth = 'Bearer %s' % EOSC_ACCESS_TOKEN
    headers['Authorization'] = auth
    LOGGER.debug('Using token: %s' % auth)

    i = 0
    while True:
        i += 1
        LOGGER.debug('Request %s...' % i)
        LOGGER.debug('Using headers: %s' % headers)
        resp = requests.request(http_verb, url, headers=headers, data=data)
        if resp.status_code == 200 or resp.status_code == 201:
            LOGGER.debug('Making authorized request to EOSC... succeeded (REALLY?). %s %s' % (resp.status_code, resp.content))
            return resp
        if resp.status_code == 401:
            LOGGER.debug('Making authorized request to EOSC... failed with HTTP 401 (Unauthorized): %s' % resp.content)
        else:
            LOGGER.warning('Making authorized request to EOSC... failed with HTTP %s: %s' % (resp.status_code, resp.content))
        
        if i <= 1:
            LOGGER.debug('Will ask for a new access token.')
            get_new_access_token()
            #eosc_access_token = get_new_access_token()
            # FOR COMPARISON:
            #import hashlib
            #md5 = hashlib.md5(eosc_access_token.encode('utf-8')).hexdigest()
            #LOGGER.debug('Got a new access token with md5sum %s' % md5)
            #LOGGER.debug('Token: %s' % eosc_access_token)
            #import datetime
            #LOGGER.debug('Time:  %s' % datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))
            #LOGGER.debug("Test md5sum on command line: printf '%s' \"TOKEN\" | md5sum")

        else:
            err_msg = 'Not asking for a new token, as we tried %s times already!' % i
            LOGGER.error(err_msg)
            raise RuntimeError(err_msg)


def update_resource(baseurl_eosc, session, service_metadata):
    # Not tested yet. TODO.
    url = baseurl_eosc.rstrip('/')+'/resource'
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    #resp = session.put(url, data=service_metadata)
    resp = make_authorized_request(url, 'PUT', headers, service_metadata)
    if not resp.status_code == 201:
        raise ValueError('Could not put resource (%s): %s' % (resp.status_code, resp.content))


def create_resource(baseurl_eosc, session, service_metadata, blue_id):
    # Not tested yet. TODO.
    url = baseurl_eosc.rstrip('/')+'/resource'
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    #resp = session.post(url, data=service_metadata)
    resp = make_authorized_request(url, 'POST', headers, service_metadata)
    if resp.status_code == 201:
        LOGGER.info('Created resource: %s %s %s' % 
            (name, resp.status_code, resp.content))
        eosc_id = resp.json()['id']
        LOGGER.info('id: %s' % eosc_id)
        return eosc_id
    else:
        raise ValueError('Could not post resource (%s): %s' %
            (resp.status_code, resp.content))



def does_resource_exist_by_id(baseurl_eosc, eosc_id, session=None):
    # Tested, works.
    LOGGER.debug('Checking whether service with eosc id "%s" already exists in EOSC catalog.' 
        % (eosc_id))

    url = baseurl_eosc+'/resource/'+eosc_id

    if session is None:
        resp = requests.get(url, headers = {"Accept": "application/json"})
    else:
        resp = session.get(url, headers = {"Accept": "application/json"})
    
    LOGGER.debug('Result: %s %s' % (resp.status_code, resp.content))
    LOGGER.debug('Result: %s %s' % (resp.status_code, resp.json()))
    if resp.status_code == 200:
        # TODO Need to check here for name?!
        return True
    elif resp.status_code == 404:
        return False
    else:
        raise RuntimeError()


def does_resource_exist_by_name(baseurl_eosc, name, resourceOrganisation, session=None):
    # Not tested yet. TODO.

    url = baseurl_eosc+'/resource/all?query='+name
    #curl -X GET --header 'Accept: application/json' 'https://api.eosc-portal.eu/resource/all?query=b2find'
    LOGGER.debug('Checking whether a service of the name "%s" already exists in EOSC catalog...' 
        % (name))
    LOGGER.debug('Check url: %s' % url)

    if session is None:
        resp = requests.get(url, headers = {"Accept": "application/json"})
    else:
        resp = session.get(url, headers = {"Accept": "application/json"})

    # TODO This is way too slow!
    #LOGGER.debug('HTTP %s: %s' % (resp.status_code, resp.content))
    if resp.status_code == 500:
        LOGGER.error('EOSC server sends error (HTTP 500): %s' % resp.json()['error'])
        # e.g.: {"url":"http://api.eosc-portal.eu/eic-registry/resource/all","error":"30,000 milliseconds timeout on connection http-outgoing-11 [ACTIVE]"}'
        # TODO Wat Nu?
        return False # This might be wrong info!


    # Iterate over hits:
    # TODO: How can we be sure we iterated over all of them - there's pagination!
    LOGGER.debug('Found %s hits!' % (resp.json()['total']))
    for item in resp.json()['results']:
        #LOGGER.debug('Looking for "%s" / "%s", found "%s" / "%s"' %
        #   (name, resourceOrganisation, item['name'], item['resourceOrganisation']))

        # Matching name:
        if item['name'] == name: 

            # Matching resourceOrganisation
            if item['resourceOrganisation'] == resourceOrganisation:
                #LOGGER.debug('Found item of matching name and resourceOrganisation: "%s", "%s"' %
                #    (name, resourceOrganisation))

                # TODO Is this enough?
                # TODO Resource Organisation might change!
                return True

            else:
                LOGGER.debug('Found item of matching name ("%s"), but wrong resourceOrganisation: "%s" (instead of "%s")' %
                    (name, item['resourceOrganisation'], resourceOrganisation))

        else:
            # Matching resourceOrganisation
            if item['resourceOrganisation'] == resourceOrganisation:
                LOGGER.debug('Found item of matching resourceOrganisation "%s", but wrong name "%s"' % (resourceOrganisation, item['name']))
                LOGGER.debug("___________")
                LOGGER.debug(item)
                LOGGER.debug("___________")

    
    LOGGER.info('No resource of name "%s" found!' % name)

    return False


if __name__ == '__main__':

    # Testing functions manually:

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s - %(name)s - %(levelname)-5s - %(message)s')
    LOGGER = logging.getLogger('catalog_interaction_eosc')
    logging.getLogger('urllib3').setLevel('WARNING')

    baseurl_eosc = 'https://api.eosc-portal.eu/'.rstrip('/')


    ###
    dummy_service_metadata = {'a': 'b'}
    dummy_service_metadata = {"id": "e5422ae1-4de6-4220-82f0-9869f2768ed3", "name": "Phytoplankton EOVs",
    "resourceOrganisation": "blue-cloud", "resourceProviders": ["d4science"],
    "webpage": "https://blue-cloud.d4science.org/web/zoo-phytoplankton_eov",
    "description": "The phytoplankton Essential Ocean Variables (EOV) service aims to provide a methodology to generate global open ocean three-dimensional (3D) gridded products of (1) chlorophyll a concentration (Chla), which is a proxy of the total phytoplankton biomass, and (2) Phytoplankton Functional Types (PFT), as a proxy for phytoplankton diversity, based on vertically-resolved in situ data of ocean physical properties (temperature and salinity) matched up with satellite products of ocean colour and sea level anomaly.",
    "tagline": "global open ocean 3D gridded chlorophyll a concentration, and Phytoplankton Functional Types",
    "logo": "https://blue-cloud.d4science.org/image/layout_set_logo?img_id=254673920", "multimedia": [], 
    "useCases": [], "scientificDomains": [{"scientificDomain": "scientific_domain-natural_sciences", 
    "scientificSubdomain": "scientific_subdomain-natural_sciences-other_natural_sciences"}], 
    "categories": [{"category": "category-processing_and_analysis-data_analysis", 
    "subcategory": "subcategory-processing_and_analysis-data_analysis-other"}], 
    "targetUsers": ["target_user-researchers", "target_user-research_communities", 
    "target_user-research_projects", "target_user-research_networks", "target_user-research_organisations", 
    "target_user-research_groups"], "accessTypes": ["access_type-virtual"], 
    "accessModes": ["access_mode-free"], "tags": ["3D", "Chla", "PFT", "Phytoplankton Functional Types", 
    "chlorophyll a concentration", "gridded products"], "geographicalAvailabilities": ["WW"], 
    "languageAvailabilities": ["en"], "resourceGeographicLocations": ["OT"], 
    "mainContact": {"firstName": "Julia", "lastName": "Uitz", "email": "julia.uitz@imev-mer.fr", 
    "phone": "", "position": "", "organisation": ""}, "publicContacts": [{"firstName": "", 
    "lastName": "", "email": "info@blue-cloud.org", "phone": "", "position": "", "organisation": ""}], 
    "helpdeskEmail": "support@d4science.org", "securityContactEmail": "admin@d4science.org", 
    "trl": "trl-7", "lifeCycleStatus": "life_cycle_status-operation", "certifications": [""], 
    "standards": [""], "openSourceTechnologies": [""], "version": "1", "lastUpdate": "", "changeLog": [""], 
    "requiredResources": [""], "relatedResources": [""], "relatedPlatforms": ["D4Science"], 
    "fundingBody": ["funding_body-ec"], "fundingPrograms": ["funding_program-h2020"], 
    "grantProjectNames": ["Blue-Cloud (Grant No.862409)"], 
    "helpdeskPage": "https://support.d4science.org/projects/blue-cloud-support", "userManual": "", 
    "termsOfUse": "https://blue-cloud.d4science.org/terms-of-use", 
    "privacyPolicy": "https://www.iubenda.com/privacy-policy/441050", "accessPolicy": "", 
    "serviceLevel": "", "trainingInformation": "", "statusMonitoring": "", "maintenance": "", 
    "orderType": "order_type-open_access", "order": "", "paymentModel": "", "pricing": ""}

    update_url = baseurl_eosc.rstrip('/')+'/resource'
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    eosc_access_token = 'eyJraWQiOiJvaWRjIiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiI1YjFkNGZmNGI2OTM0YT'+\
        'EwYjNlNWFmM2Y3YWE1M2FkN0Bld...r617HuGR67Ap9U028mg_edEODoSggnMAaoWF4_J7qTAVQPCA5n_yn22ew'+\
        'BdEqh191QMqQ'
    resp = make_authorized_request(update_url, 'PUT', eosc_access_token, headers, dummy_service_metadata)
    print('Done')
    import sys
    sys.exit()

    ### Testing does_resource_exist_by_id
    LOGGER.info('___________________________________________________________')
    LOGGER.info('Testing: does_resource_exist_by_id')
    eosc_id = 'blue-cloud.phytoplankton_eovs'
    res = does_resource_exist_by_id(baseurl_eosc, eosc_id)
    LOGGER.info('Result: %s' % res)

    ### Testing does_resource_exist_by_name
    LOGGER.info('___________________________________________________________')
    LOGGER.info('Testing: does_resource_exist_by_name')
    resourceOrganisation = "blue-cloud"
    name = "phytoplankton_eovs"
    res = does_resource_exist_by_name(baseurl_eosc, name, resourceOrganisation)
    LOGGER.info('Result: %s' % res)

    ### Testing does_resource_exist_by_name
    #LOGGER.info('___________________________________________________________')
    #LOGGER.info('Testing: does_resource_exist_by_name')
    #resourceOrganisation = "Bjerknes Climate Data Centre, Geophysical Institute, University of Bergen"
    #name = "carbon_data_notebooks"
    #res = does_resource_exist_by_name(baseurl_eosc, name, resourceOrganisation)
    #LOGGER.info('Result: %s' % res)
