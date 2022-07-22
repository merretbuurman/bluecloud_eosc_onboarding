#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import logging
import requests
import json
import datetime
import argparse
import catalog_interaction_eosc as eosc
import catalog_interaction_blue as blue
import integration
import utils
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


PROGRAM_DESCRIP = 'TODO'
VERSION = 20220721

MIN_TRL = 7


def treat_vre(baseurl_blue, baseurl_eosc, session, vre_name, blue_token):
	LOGGER.info('Treating VRE "%s"' % vre_name)
	
	# Which services?
	service_names = blue.find_service_names_per_vre(blue_token, baseurl_blue, session)
	LOGGER.info('Services found: %s' % service_names)
	# For testing:
	#service_names = [
	#  'oceanpatterns',
	#  'mei_generator',
	#  'carbon_data_notebooks',
	#  'storm_severity_index_ssi_notebook_',
	#  'oceanregimes_notebooks',
	#  'modelling_phyto_zoo_plankton_interactions',
	#  'zooplankton_eovs',
	#  'phytoplankton_eovs',
	#  'marine_environmental_indicators_vlab',
	#  'zoo-_and_phytoplankton_essential_ocean_variable_products_vlab',
	#  'zoo_and_phytoplankton_essential_ocean_variable_products_vlab',
	#]

	# This one should be ready for onboarding!!
	#service_names = ['oceanpatterns']
	# The one already onboarded via GUI:
	#service_names = ['phytoplankton_eovs']
	service_names=[]

	LOGGER.info('Services found: %s' % service_names)

	# Get the metadata for each service:
	collected_eosc_metadata = []
	to_file = True
	i = 0
	for service_name in service_names:
		i += 1
	
		LOGGER.info('___________________________________________________')
		LOGGER.info('Treating service %s/%s: "%s"' % (i, len(service_names), service_name))
		
		# Get and map:
		eosc_metadata = integration.get_and_convert_metadata(baseurl_blue, baseurl_eosc,
			service_name, session, vre_name, blue_token, to_file)
		collected_eosc_metadata.append(eosc_metadata)

		# Validate it:
		LOGGER.debug('Now trying validation')
		eosc.validate_service_metadata(eosc_metadata, VALIDATION_URL, True)

		# Filter those services that have TRL < 7
		trl_int = int(eosc_metadata['trl'].replace('trl-', ''))
		if trl_int < MIN_TRL:
			LOGGER.warning('TRL %s is <%s, so the service should not be visible.' % 
				(trl_int, MIN_TRL))
		else:
			LOGGER.debug('TRL is ok: %s' % trl_int)

			#############################
			### Push to EOSC catalog: ###
			#############################
			integration.update_or_create_at_eosc(service_name, baseurl_blue, baseurl_eosc,
				session, vre_name, eosc_metadata)

		LOGGER.info('That was service %s/%s: "%s"' % (i, len(service_names), service_name))

		# Useful for debugging: Stop and wait after each service:
		if True:
			yesno = input('Next service? Type any key')
			if len(yesno) >= 0:
				pass

	# Useful for debugging: Compare all passed values for one VRE:
	if False:
		utils.compare_values_of_services(collected_eosc_metadata, vre_name)

	# Final:
	LOGGER.info('___________________________________________________')
	LOGGER.info('This was VRE "%s"' % vre_name)
	LOGGER.info('Services: %s' % service_names)







###
### Main
###

if __name__ == '__main__':

	parser = argparse.ArgumentParser(description=PROGRAM_DESCRIP)
	parser.add_argument('--version', action='version', version='Version: %s' % VERSION)
	parser.add_argument("-v","--verbose", action="store_true") # only true/false
	parser.add_argument("-vre","--vre", action="append", help='Which VREs to process? Type "mei" and or "plankton" Several are possible.')
	myargs = parser.parse_args()

	all_vres = myargs.vre
	if all_vres is None:
		print('Please provide option --vre. Exiting.')
		sys.exit()


	###############
	### Logging ###
	###############

	if myargs.verbose:
		logging.basicConfig(level=logging.DEBUG, format='%(name)10s - %(levelname)-5s - %(message)s')
	else:
		logging.basicConfig(level=logging.INFO, format='%(asctime)-15s - %(name)s - %(levelname)-5s - %(message)s')
	LOGGER = logging.getLogger('mainscript')
	logging.getLogger('urllib3').setLevel('WARNING')


	###############
	### Constants. TODO NOT TO BE HARDCODED ###
	###############

	baseurl_blue = BLUE_CLOUD_API_BASE_URL.rstrip('/')
	baseurl_eosc = EOSC_API_BASE_URL.rstrip('/')


	#################
	### Let's go! ###
	#################

	session = requests.Session()

	blue_secret = os.environ.get('BLUE_SECRET')
	blue_client_id = os.environ.get('BLUE_CLIENT_ID')
	#print('eosc_token: %s' % eosc_token)
	#print('blue_secret: %s' % blue_secret)
	#print('blue_client_id: %s' % blue_client_id)

	if 'mei' in all_vres:
		blue_token = blue.get_jwt_token(blue_client_id, blue_secret, 'MarineEnvironmentalIndicators')
		#print('TOKEN: %s' % blue_token)
		treat_vre(baseurl_blue, baseurl_eosc, session,
			'marineenvironmentalindicators', blue_token)
		#5 Services found: ['carbon_data_notebooks', 'storm_severity_index_ssi_notebook_', 'oceanregimes_notebooks', 'oceanpatterns', 'mei_generator']
		all_vres.remove('mei')

	if 'plankton' in all_vres:
		blue_token = blue.get_jwt_token(blue_client_id, blue_secret, 'Zoo-Phytoplankton_EOV')
		#print('TOKEN: %s' % blue_token)
		treat_vre(baseurl_blue, baseurl_eosc, session,
			'zoo-phytoplankton_eov', blue_token)
		#4 Services found: ['phytoplankton_eovs', 'modelling_phyto_zoo_plankton_interactions', 'zoo-_and_phytoplankton_essential_ocean_variable_products_vlab', 'zooplankton_eovs']
		all_vres.remove('plankton')



	#treat_vre(baseurl_blue, baseurl_eosc, session, 'blue-cloudlab', token_blue_cloudlab, eosc_token, compare)
	# Services found: ['jupyter_hub', 'rstudio', 'analytics_engine']
	
	#treat_vre(baseurl_blue, baseurl_eosc, session, 'aquacultureatlasgeneration', token_aquacultureatlasgeneration, eosc_token, compare)
	# Services found: []
	
	#treat_vre(baseurl_bc, baseurl_eosc, session, 'planktongenomics', token_planktongenomics, eosc_token)
	# Services found: []

	#treat_vre(baseurl_bc, baseurl_eosc, session, 'bluecloud whatever', token_bluecloud, eosc_token)
	# Services found: []

	if len(all_vres) > 0:
		LOGGER.warning('Could not recognize vre name(s): %s. Ignoring. Please pass valid names.' % ', '.join(all_vres))



# Usage:
# source secrets.sh
# python mainscript.py -v --vre mei --vre plankton
