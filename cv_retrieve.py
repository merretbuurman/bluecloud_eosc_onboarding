#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import logging
import requests
import json

'''
Module containing functions to retrieve Controlled Vocabularies
from the EOSC vocabulary API.


Merret Buurman, DKRZ, April 2022
Developed in the scope of the Blue-Cloud project.
'''

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

### Import the scientific domains once upon module import!
VOCAB_URL = 'https://beta.providers.eosc-portal.eu/api/vocabulary/byType' # TODO Beta
PROVIDERS_URL = 'https://api.eosc-portal.eu/provider/'


def get_providers_old(providers_url=None):
    '''
    Function to retrieve all providers that are currently onboarded in EOSC:
    Their ids and how they are mapped to names and abbreviations.
    '''
    ids = []
    fetch_num = 1000
    # TODO: Eventually there might be more than 1000, then stuff gets more complicated!

    if providers_url is None:
        providers_url = PROVIDERS_URL.rstrip()

    resp = requests.get('%s/all?quantity=%s' % (providers_url, fetch_num))
    if resp.status_code == 500:
        LOGGER.error('Server error (http %s) when trying to retrieve providers: %s' % (resp.status_code, resp.content))
        return None

    resp_json = resp.json()
    LOGGER.debug('Iterating through providers %s to %s of %s' % (resp_json['from'], resp_json['to'], resp_json['total']))
    for item in resp_json['results']:
        ids.append(item['id'])

    print('done! %s items' % len(ids))
    return ids, names_ids, abbrev_ids

def get_providers(providers_url=None):
    '''
    Function to retrieve all providers that are currently onboarded in EOSC.
    The function returns two results:
    * A dictionary listing the id for each name
    * A dictionary listing the id for each abbreviation

    This way, we can check whether an id is existing, or we can retrieve the
    id given a name or abbreviation.
    '''
    names_ids = {}
    abbrev_ids = {}
    fetch_num = 1000
    # TODO: Eventually there might be more than 1000, then stuff gets more complicated!

    if providers_url is None:
        providers_url = PROVIDERS_URL.rstrip()

    LOGGER.debug('Retrieving providers from EOSC vocabulary API...')
    resp = requests.get('%s/all?quantity=%s' % (providers_url, fetch_num))
    if resp.status_code == 500:
        LOGGER.error('Server error (http %s) when trying to retrieve providers: %s' % (resp.status_code, resp.content))
        return None, None

    resp_json = resp.json()
    LOGGER.debug('Iterating through providers %s to %s of %s' % (resp_json['from'], resp_json['to'], resp_json['total']))
    for item in resp_json['results']:
        names_ids[item['name']] = item['id']
        abbrev_ids[item['abbreviation']] = item['id']

    LOGGER.debug('Retrieving providers from EOSC vocabulary API... done (%s items)' % len(names_ids.values()))
    return names_ids, abbrev_ids


def get_cv_values(api):
    values = {}
    resp = requests.get(VOCAB_URL+'/'+api.lstrip('/'))
    #LOGGER.debug('%s response: %s %s' % (api.lower(), resp.status_code, resp.content))
    for item in resp.json():
        values[item['name'].lower()] = item['id']
    LOGGER.info('Found %s values of CV "%s"' % (len(values), api.lower()))
    return values


def get_values_and_subvalues(api_super, api_sub):
    '''
    CV_main:    Dictionary: category name (lowercase) => id.
    CV_sub:     Dictionary: category name.subcategory name => id. ??
    CV_mapping: Dictionary: category id => list of subcategory ids.
    '''
    CV_main = {}
    CV_sub = {}
    CV_mapping = {}

    # Getting all values of the main category:
    resp = requests.get(VOCAB_URL+'/'+api_super.lstrip('/'))
    for item in resp.json():
        # Note: Making the names lower case, because e.g. "Other Natural Sciences" vs "Other natural sciences"
        mainid = item['id']
        mainname = item['name'].lower()
        CV_main[mainname] = mainid
        CV_mapping[mainid] = []

    LOGGER.info('Found %s values of CV "%s"' % (len(CV_main), api_super.lower()))
    #LOGGER.debug('%s: values (%s): %s' % (api_super.lower(), len(CV_main), CV_main))

    # Getting all values of the sub category:
    resp = requests.get(VOCAB_URL+'/'+api_sub.lstrip('/'))
    for item in resp.json():
        subid = item['id']
        subname = item['name'].lower()
        parentid = item['parentId']

        if parentid is None:
            LOGGER.warning('%s: Skipping sub category with no parent id: %s' % (api_super.lower(), item))
            continue

        # We need to construct a key that is a combination of category and subcategory,
        # as subcategory names are not unique. There are many subcategories "Other", for example.
        for tempname, tempid in CV_main.items():
            if tempid == parentid:
                key = tempname+'.'+subname
        
        CV_sub[key] = subid
        CV_mapping[parentid].append(subid)

    LOGGER.info('Found %s values of CV "%s"' % (len(CV_sub), api_sub.lower()))
    #LOGGER.debug('%s: sub-values (%s): %s' % (api_sub.lower(), len(CV_sub), CV_sub))
    #LOGGER.debug('%s: mapping: %s' % (api_sub.lower(), CV_mapping))

    return CV_main, CV_sub, CV_mapping


def get_values_and_subvalues2(api_super, api_sub):
    '''
    CV_main:    Dictionary: category name (lowercase) => id.
    CV_sub:     Dictionary: category name.subcategory name => id. ??
    CV_mapping: Dictionary: subcategory id => category id.
    '''
    CV_main = {}
    CV_sub = {}
    CV_mapping = {}

    # Getting all values of the main category:
    resp = requests.get(VOCAB_URL+'/'+api_super.lstrip('/'))
    for item in resp.json():
        # Note: Making the names lower case, because e.g. "Other Natural Sciences" vs "Other natural sciences"
        mainid = item['id']
        mainname = item['name'].lower()
        CV_main[mainname] = mainid

    LOGGER.info('Found %s values of CV "%s"' % (len(CV_main), api_super.lower()))
    #LOGGER.debug('%s: values (%s): %s' % (api_super.lower(), len(CV_main), CV_main))

    # Getting all values of the sub category:
    resp = requests.get(VOCAB_URL+'/'+api_sub.lstrip('/'))
    for item in resp.json():
        subid = item['id']
        subname = item['name'].lower()
        parentid = item['parentId']

        if parentid is None:
            LOGGER.warning('%s: Skipping sub category with no parent id: %s' % (api_super.lower(), item))
            continue

        # We need to construct a key that is a combination of category and subcategory,
        # as subcategory names are not unique. There are many subcategories "Other", for example.
        for temp_mainname, temp_mainid in CV_main.items():
            if temp_mainid == parentid:
                key = temp_mainname+'.'+subname
        
        CV_sub[key] = subid
        CV_mapping[subid] = parentid

    LOGGER.info('Found %s values of CV "%s"' % (len(CV_sub), api_sub.lower()))
    #LOGGER.debug('%s: sub-values (%s): %s' % (api_sub.lower(), len(CV_sub), CV_sub))
    #LOGGER.debug('%s: mapping: %s' % (api_sub.lower(), CV_mapping))

    if True:
        LOGGER.debug('Printing to file: %s' % api_super)
        filename = '_cv_%s_mapping.json' % (api_super.lower())
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(CV_mapping, f, ensure_ascii=False, indent=4)
            # Subcategory ID : Category ID
            # Subdomain ID :   Domain ID

        filename = '_cv_%s.json' % (api_super.lower())
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(CV_main, f, ensure_ascii=False, indent=4)
            # Category name: Category ID
            # Domain name:   Domain ID

        filename = '_cv_%s_sub.json' % (api_super.lower())
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(CV_sub, f, ensure_ascii=False, indent=4)
            # Category name -dot- Subcategory name: Subcategory ID
            # Domain name -dot- Subdomain name:     Subdomain ID


    return CV_main, CV_sub, CV_mapping

def print_cv(title, cv_dict, logfunc):
    logfunc('CV %s' % title)
    for k,v in cv_dict.items():
        logfunc('  * %15s: %s' % (k, v))

if __name__ == '__main__':

    # Try retrieving these controlled vocabularies:
    #logging.basicConfig(level=logging.DEBUG, format='%(name)10s - %(levelname)-5s - %(message)s')
    logging.basicConfig(level=logging.INFO, format='%(name)10s - %(levelname)-5s - %(message)s')

    ACCESS_MODES = get_cv_values('ACCESS_MODE')
    ACCESS_TYPES = get_cv_values('ACCESS_TYPE')
    LIFE_CYCLE_STATUS = get_cv_values('LIFE_CYCLE_STATUS')
    COUNTRIES    = get_cv_values('COUNTRY')
    FUNDING_BODIES = get_cv_values('FUNDING_BODY')
    FUNDING_PROGRAMS = get_cv_values('FUNDING_PROGRAM')
    ORDER_TYPES = get_cv_values('ORDER_TYPE')
    print_cv('ORDER_TYPES', ORDER_TYPES, LOGGER.debug)

    CV_DOM, CV_subDOM, CV_DOM_MAPPING = get_values_and_subvalues('SCIENTIFIC_DOMAIN', 'SCIENTIFIC_SUBDOMAIN')
    CV_CAT, CV_subCAT, CV_CAT_MAPPING = get_values_and_subvalues('CATEGORY', 'SUBCATEGORY')

    #print('%s \n\n%s' % (CV_CAT, CV_subCAT))


    '''
    Example output, April 2022:
    [merret@localhost bluecloud_eosc]$ python cv_retrieve.py 
      __main__ - INFO  - Found 5 values of CV "access_mode"
      __main__ - INFO  - Found 5 values of CV "access_type"
      __main__ - INFO  - Found 14 values of CV "life_cycle_status"
      __main__ - INFO  - Found 127 values of CV "funding_body"
      __main__ - INFO  - Found 82 values of CV "funding_program"
      __main__ - INFO  - Found 8 values of CV "scientific_domain"
      __main__ - INFO  - Found 45 values of CV "scientific_subdomain"
      __main__ - INFO  - Found 20 values of CV "category"
      __main__ - INFO  - Found 145 values of CV "subcategory"

    '''
