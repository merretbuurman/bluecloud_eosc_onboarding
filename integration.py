#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import logging
import requests
import json
import datetime
import argparse
import catalog_interaction_eosc as eosc
import catalog_interaction_blue as blue
import mapping
import os
import sys

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


'''

Draft of an API to keep Blue-Cloud services up to date
in EOSC marketplace.

To be run as cronjob in a container?

EOSC Marketplace API:
https://providers.eosc-portal.eu/openapi

First Draft:
Merret, DKRZ, 2022-03


Catalogue containing all services:
https://blue-cloud.d4science.org/catalogue-bluecloud

* Marine Environmental Indicators (5 services)
* Zoo-Phytoplankton EOV (4 services)
* Blue-Cloud Lab (3 services)

Get to them to retrieve tokens:
https://blue-cloud.d4science.org/explore

* MarineEnvironment...		https://blue-cloud.d4science.org/group/marineenvironmentalindicators/communication
* Zoo-Phytoplankton_EOV		https://blue-cloud.d4science.org/group/zoo-phytoplankton_eov/communication
* Blue-CloudLab 			https://blue-cloud.d4science.org/group/blue-cloudlab
* PlanktonGenomics          https://blue-cloud.d4science.org/group/planktongenomics
* FisheriesAtlas            -- waiting approval --
* GRSF_Pre                  -- waiting approval --
* AquacultureAtlasG...      https://blue-cloud.d4science.org/group/aquacultureatlasgeneration    

'''

# Beta:
# Swagger page/GUI:
'https://beta.providers.eosc-portal.eu/openapi'
# Requests to:
'https://beta.providers.eosc-portal.eu/api/vocabulary/byType/SUBCATEGORY'
'https://beta.providers.eosc-portal.eu/api/resource/validate'

# Public:
# Swagger page/GUI:
'https://providers.eosc-portal.eu/openapi/' 
# Requests to:
'https://api.eosc-portal.eu/'

EOSC_API_BASE_URL = 'https://providers.eosc-portal.eu/openapi/' # down on 2022-04-15
EOSC_API_BASE_URL = 'https://api.eosc-portal.eu/'
#EOSC_API_BASE_URL = 'https://beta.providers.eosc-portal.eu/api/vocabulary/byType/SUBCATEGORY'
BLUE_CLOUD_API_BASE_URL = 'https://blue-cloud.d4science.org/catalogue-bluecloud/'
BLUE_CLOUD_API_BASE_URL = 'https://api.d4science.org/catalogue/'
VALIDATION_URL = 'https://api.eosc-portal.eu/resource/validate/' # public
#VALIDATION_URL = 'https://beta.providers.eosc-portal.eu/api/resource/validate/' # beta, no point, does not know blue-cloud...
EOSC_REFRESH_URL  = 'https://aai.eosc-portal.eu/oidc/token'
PRIMARY_KEY_MAPPING_FILE = 'bluecloud_id_eosc_id.txt'








def write_id_to_file(blue_id, service_name, eosc_id, eosc_title):
	'''
	Tested, works.
	date;service_name;bluecloud_id;eosc_id
	2022-06-13_17:31:09;phytoplankton_eovs;e5422ae1-4de6-4220-82f0-9869f2768ed3;blue-cloud.phytoplankton_eovs
	'''

	if eosc_id is None:
		return False

	# Write file header
	if not os.path.isfile(PRIMARY_KEY_MAPPING_FILE):
		with open(PRIMARY_KEY_MAPPING_FILE, 'a') as fi:
			line = 'date;service_name;bluecloud_id;eosc_id;eosc_title'
			fi.write(line+'\n')

	line = '%s;%s;%s;%s'% (service_name, blue_id, eosc_id, eosc_title)

	# Check if already in?
	with open(PRIMARY_KEY_MAPPING_FILE) as fi:
	    if line in fi.read():
	        LOGGER.debug('Key file already contains %s' % line)
	        return

	# Otherwise write!
	with open(PRIMARY_KEY_MAPPING_FILE, 'a') as fi:
		now = datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
		fi.write(now+';'+line+'\n')
		LOGGER.debug('Written eosc id into key file ("%s").' % line)


def get_eosc_id_from_file(blue_id):
	'''
	Tested, works.
	date;service_name;bluecloud_id;eosc_id
	2022-06-13_17:31:09;phytoplankton_eovs;e5422ae1-4de6-4220-82f0-9869f2768ed3;blue-cloud.phytoplankton_eovs
	'''
	try:
		with open(PRIMARY_KEY_MAPPING_FILE, 'r') as fi:
			for line in fi:
				if line.split(';')[2] == blue_id:
					eosc_id = line.split(';')[3].strip()
					LOGGER.debug('Found eosc id: "%s" (for blue-cloud id "%s").' % (eosc_id, blue_id))
					return eosc_id
	
	except FileNotFoundError as e:
		pass

	LOGGER.debug('Did not find eosc id: for blue-cloud id "%s".' % (blue_id))
	return None


def write_metadata_to_json_file(vre_name, service_name, service_metadata, bc_or_eosc):
	filename = 'stored_metadata/_service_%s___%s.%s.json' % (vre_name, service_name.replace('-', ''), bc_or_eosc)
	with open(filename, 'w', encoding='utf-8') as f:
		json.dump(service_metadata, f, ensure_ascii=False, indent=4)
		LOGGER.debug('Stored %s metadata of service to file: "%s"' %
			(bc_or_eosc, filename))


def get_and_convert_metadata(baseurl_blue, baseurl_eosc, service_name, session, vre_name, blue_token, tofile=True):

	service_metadata = blue.get_metadata_one_service(service_name, blue_token, baseurl_blue, session)

	# Write it to json file:
	if tofile:
		write_metadata_to_json_file(vre_name, service_name, service_metadata, 'bc')

	# Map it to EOSC format:
	eosc_metadata = mapping.extract_bluecloud_metadata(service_metadata)

	# Write it to json file:
	if tofile:
		write_metadata_to_json_file(vre_name, service_name, eosc_metadata, 'mapped')
		return eosc_metadata


def update_or_create_at_eosc(service_name, baseurl_blue, baseurl_eosc, session, vre_name, eosc_service_metadata, dry_run=False):

	# Does this already exist at EOSC?
	# TODO can we just try to create and see what happens?
	does_exist = None
	blue_id = eosc_service_metadata['blue_id']
	eosc_id = get_eosc_id_from_file(blue_id)
	eosc_service_metadata['id'] = eosc_id
	#del eosc_service_metadata['blue_id']
	eosc_title = eosc_service_metadata['name']
	if dry_run:
		return

	if eosc_id is not None:
		LOGGER.debug('Did find an eosc id: "%s". Checking if service exists.' % eosc_id)
		does_exists = eosc.does_resource_exist_by_id(baseurl_eosc, eosc_id, session)
	else:
		# This method is slow and unreliable and relies on name and organisation being the same.
		# TODO Not tested?
		LOGGER.debug('Did not find an eosc id. Checking if service exists, by name and resource organisation.')
		resourceOrganisation = eosc_service_metadata['resourceOrganisation']
		does_exists = eosc.does_resource_exist_by_name(baseurl_eosc, service_name,
			resourceOrganisation, session)

	if does_exists:
		LOGGER.info('Service "%s" already exists.' % service_name)
		# TODO: Do we need to check whether any change has occurred?
		# E.g. via revision_id or metadata_changed timestamp?
		#eosc.validate_service_metadata(eosc_metadata, VALIDATION_URL)
		print('\n\n#########################################################')
		eosc_service_metadata['id'] = eosc_id
		print(json.dumps(eosc_service_metadata))
		print('#########################################################\n\n')
		eosc.update_resource(baseurl_eosc, session, eosc_service_metadata)
	else:
		LOGGER.info('Service "%s" does not exist yet.' % service_name)
		# TODO: Integrity/compatibility check
		eosc_id = eosc.create_resource(baseurl_eosc, session, eosc_service_metadata, blue_id)
		print('########################################')
		print('### EOSC ID: %s (for %s) ###' % (eosc_id, service_name))
		print('########################################')
		write_id_to_file(blue_id, service_name, eosc_id, eosc_title)
		return eosc_id


###
### Main
###

if __name__ == '__main__':
	# Just for testing!

	'''
	# Testing
	eosc_id = 'blue-cloud.phytoplankton_eovs'
	blue_id = 'e5422ae1-4de6-4220-82f0-9869f2768ed3'
	service_name = 'phytoplankton_eovs'
	blue_title = 'Phytoplankton EOVs'
	write_id_to_file(blue_id, service_name, eosc_id, eosc_title)
	res = get_eosc_id_from_file(blue_id)
	print('Result: %s' % res)
	import sys
	sys.exit()
	'''