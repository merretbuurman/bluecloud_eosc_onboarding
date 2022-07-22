#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import requests
import logging
import base64

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

FILE_LAST_CHANGED = 20220621
USE_GCUBE_TOKEN = False
AUDIENCES = ['MarineEnvironmentalIndicators', 'Blue-CloudProject', 'Blue-CloudLab',
             'FisheriesAtlas', 'PlanktonGenomics', 'Zoo-Phytoplankton_EOV']


'''
Interaction with the Blue-Cloud service catalogue.
The base url is currently:
https://api.d4science.org/catalogue/

Merret Buurman, DKRZ, 2022-04-12
'''

def find_service_names_per_vre(token, baseurl, session=None, use_gcube=False):
	if use_gcube or USE_GCUBE_TOKEN:
		# Tested, works.
		h = {'gcube-token': token, 'Accept': 'application/json', 'Content-Type': 'application/json'}
	else:
		h = {'Authorization': token, 'Accept': 'application/json', 'Content-Type': 'application/json'}

	url = baseurl + '/items?q=extras_systemtype:Service'
	LOGGER.debug('Checking for services at BC: %s' % url)
	if session is None:
		resp = requests.get(url, headers=h)
	else:
		resp = session.get(url, headers=h)
	LOGGER.debug('Result: %s %s' % (resp.status_code, resp.json()))
	service_names = resp.json()
	return service_names


def get_metadata_one_service(service_name, token, baseurl, session=None, use_gcube=False):
	url = baseurl +'/items/'+service_name
	LOGGER.debug('Requesting metadata for service %s at %s' % (service_name, url))

	if use_gcube or USE_GCUBE_TOKEN:
		# Tested, works.
		LOGGER.debug('Using the gCube token for auth.')
		h = {'gcube-token': token, 'Accept': 'application/json', 'Content-Type': 'application/json'}
	else:
		LOGGER.debug('Using the service account token for auth.')
		h = {'Authorization': token, 'Accept': 'application/json', 'Content-Type': 'application/json'}
	
	if session is None:
		resp = requests.get(url, headers=h)
	else:
		resp = session.get(url, headers=h)
	
	LOGGER.debug('Response: %s' % resp.status_code)
	#LOGGER.debug('Response: %s %s' % (resp.status_code, resp.content))
	metadata = resp.json()
	return metadata


def get_jwt_token(clientid, secret, audience):
	# See docs: https://dev.d4science.org/using-service-accounts
	token_url = 'https://accounts.d4science.org/auth/realms/d4science/protocol/openid-connect/token'
	LOGGER.debug('Requesting for token at: %s' % token_url)
	tmp = '%s:%s' % (clientid, secret)
	tmpbase64 = base64.b64encode(bytes(tmp, 'utf-8'))
	strbase64 = tmpbase64.decode("utf-8")
	LOGGER.debug('Auth string: %s' % strbase64)
	#LOGGER.debug('Auth string: %s (type %s)' % (strbase64, type(strbase64)))
	auth_str = 'Basic %s' % str(strbase64)
	hea = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': auth_str}

	if audience not in AUDIENCES:
		raise ValueError('Audience "%s" not valid, expecting one of: %s' % AUDIENCES)

	payload_json = {}
	payload_json['grant_type'] = 'urn:ietf:params:oauth:grant-type:uma-ticket'
	payload_json['audience'] = '%2Fd4science.research-infrastructures.eu%2FD4OS%2F'+audience
	#LOGGER.debug('POST payload: %s' % payload_json)

	resp = requests.post(token_url, headers=hea, data=payload_json)
	#LOGGER.debug('Status code: %s' % resp.status_code)
	#LOGGER.debug('Status code: %s. Response: %s' % (resp.status_code, resp.content))

	if resp.status_code == 200:
		bearer_token = resp.json()['access_token']
		bearer_token_complete = 'Bearer %s' % bearer_token
		return bearer_token_complete
	else:
		# Some error!
		msg = 'Error (HTTP %s) when retrieving authorization token from d4science: %s' % (resp.status_code, resp.content)
		raise RuntimeError(msg)



if __name__ == '__main__':

	# Just for testing.
	logging.basicConfig(level=logging.DEBUG)


	# Test get_jwt_token():
	clientid = 'Blue-Cloud-EOSC-onboarding'
	secret = 'xyz' # 
	audience = 'MarineEnvironmentalIndicators'
	token = get_jwt_token(clientid, secret, audience)
	LOGGER.debug('D4Science token: %s' % token)


	# Test find_service_names_per_vre()
	baseurl = 'https://api.d4science.org/catalogue'
	token_marineenvironmentalindicators = 'xyz'
	x = find_service_names_per_vre(token_marineenvironmentalindicators, baseurl, None, True)
	LOGGER.debug('Service names for VRE: %s' % x)


	# Test get_metadata_one_service()
	baseurl = 'https://api.d4science.org/catalogue'
	token_marineenvironmentalindicators = 'xyz'
	service_name = 'oceanpatterns'
	md = get_metadata_one_service(service_name, token_marineenvironmentalindicators, baseurl, None, True)
	LOGGER.debug('Metadata for service %s: %s (...)' % (service_name, str(md)[:200]))



