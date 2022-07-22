#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import datetime
import logging
import requests
import cv_retrieve

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

FILE_CHANGED = 20220721

###############################
### Controlled vocabularies ###
###############################

# (global variables, filled only once)
# FIXME: Not urgent: Use a class for the metadata, these as class vars
PROVIDER_IDS = None
TARGET_USERS = None
ACCESS_MODES = None
ACCESS_TYPES = None
LIFE_CYCLE_STATUS = None
COUNTRIES = None
ORDER_TYPES = None
FUNDING_BODIES = None
FUNDING_PROGRAMS = None
CV_DOM, CV_SUBDOM, CV_DOM_MAPPING = None, None, None
CV_CAT, CV_SUBCAT, CV_CAT_MAPPING = None, None, None

ABBREVIATIONS = {
    'oceanregimes_notebooks': 'oceanregimes',
    'oceanpatterns': 'oceanpatterns',
    'mei_generator': 'mei_generator', 
    'carbon_data_notebooks': 'carbon_notebooks',
    'storm_severity_index_ssi_notebook_': 'storm_ssi',
    'marine_environmental_indicators_vlab': 'mei_vlab',
    'modelling_phyto_zoo_plankton_interactions': 'plankton_interact',
    'zooplankton_eovs': 'zooplankton_eovs',
    'zoo-_and_phytoplankton_essential_ocean_variable_products_vlab': 'plankton_eov_vlab'
}


####################
### Function def ###
####################

def log_value(logger, val, name):
    print_empty = False

    if val is None or len(val) == 0:
        if print_empty:
            logger.debug(' | %s: "%s" ' % (name, val))
    else:
        logger.debug(' | %s: "%s" ' % (name, val))

def check_is_date(val, name, mandatory, collected_messages):
    # TODO ASK TRY OUT: Note that I have contradictory info about the format!
    # '%d/%m/%Y' according to https://eosc-portal.eu/sites/default/files/3-EOSC-Portal-Provider-and-Resource-Profiles-Tutorial-v1-2020-09-30.pptx.pdf
    # '%Y-%m-%d' or '%Y-%d-%m' according to https://providers.eosc-portal.eu/openapi

    if not isinstance(val, str):
        msg = 'Must be a date and type string: "%s" ("%s", type "%s")' % (name, val, type(val))
        collected_messages.append(msg)
        return False

    if len(val) == 0 and mandatory:
        msg = 'Must be a date and non-zero length: "%s" ("%s", length %s)' % (name, val, len(val))
        collected_messages.append(msg)
        return False

    if len(val) == 0 and not mandatory:
        # Cannot parse, just leave empty...
        return True

    #desired_format = '%d/%m/%Y'
    desired_format = '%Y-%m-%d'
    try:
        datetime.datetime.strptime(val, desired_format)
    except ValueError as e:
        msg = 'Malformed date: "%s" ("%s"), error: "%s", desired format: "%s"' % (name, val, e, desired_format)
        collected_messages.append(msg)
        return False

    return True

def check_is_email(val, name, mandatory, collected_messages):
  
    if not isinstance(val, str):
        msg = 'Must be an email and type string: "%s" ("%s", type "%s")' % (name, val, type(val))
        collected_messages.append(msg)
        return False

    if len(val) == 0 and mandatory:
        msg = 'Must be an email and non-zero length: "%s" ("%s", length %s)' % (name, val, len(val))
        collected_messages.append(msg)
        return False

    if not '@' in val:
        msg = 'Email address must contain "@": "%s" ("%s")' % (name, val)
        collected_messages.append(msg)
        return False

    return True

def check_is_string(val, name, mandatory, max_len, collected_messages):

    if not isinstance(val, str):
        msg = 'Must be string: "%s" ("%s", type: "%s")' % (name, val, type(val))
        collected_messages.append(msg)
        return False

    if len(val) == 0 and mandatory:
        msg = 'Must have non-zero length: "%s" ("%s", length %s)' % (name, val, len(val))
        collected_messages.append(msg)
        return False
    
    if max_len is not None and len(val) > max_len:
        msg = 'Length must be max %s (is %s): "%s" ("%s")!' % (max_len, len(val), name, val)
        collected_messages.append(msg)
        return False

    return True

def check_is_in_cv(val, name, mandatory, cv, cv_name):

    if not isinstance(val, str):
        msg = 'Must be string: "%s" ("%s", type: "%s")' % (name, val, type(val))
        LOGGER.error(msg)
        return False

    if len(val) == 0 and mandatory:
        LOGGER.warning('Must have non-zero length: "%s" ("%s", length %s)' % (name, val, len(val)))
        return False

    if val not in cv:
        msg = 'Must be in the controlled vocabulary: "%s" ("%s"), must be in %s' % (name, val, cv_name)
        LOGGER.error(msg)
        return False

    return True

def check_is_url(val, name, mandatory, collected_messages):

    if not isinstance(val, str):
        msg = 'Must be a URL and type string: "%s" ("%s", type "%s")' % (name, val, type(val))
        collected_messages.append(msg)
        return False

    if len(val) == 0:
        if mandatory:
            msg = 'Must be a URL and non-zero length: "%s" ("%s", length %s)' % (name, val, len(val))
            collected_messages.append(msg)
            return False
        else:
            return True

    if not val.startswith('http'):
        msg = 'Must be a URL: "%s" ("%s")' % (name, val)
        collected_messages.append(msg)
        return False

    return True

def get_name_from_val(val, name, collected_messages):
    # Hoping there will be just one first and one last name:

    if not isinstance(val, str):
        msg = 'Must be string: "%s" ("%s", type "%s")' % (name, val, type(val))
        collected_messages.append(msg)
        return False

    # For cases like: "Noteboom, Jan Willem", "Palermo, Francesco"
    if ', ' in val:
        temp = val.strip().split(', ')
        if len(temp) == 2:
            lastName, firstName = temp
            return firstName, lastName

    # For cases like: "Kevin Balem"
    if len(val)>0: LOGGER.warning('Name not comma-separated: "%s"' % val)
    temp = val.strip().split(' ')
    if len(temp) == 2:
        firstName, lastName = temp
        return firstName, lastName
    elif len(temp) == 3:
        firstName = temp[0]+' '+temp[1]
        lastName = temp[2]
        # TODO: Wild guess that person has two first names and one last name
        msg = 'Malformed name, three names: Assuming that two are first names and one is last name: "%s" ("%s")' % (name, val)
        collected_messages.append(msg)
        return firstName, lastName

    elif len(temp) == 1 and len(val) == 0:
        # No name given!
        return '', ''

    elif len(temp) == 1:
        # One name given!
        # TODO: Wild guess, assuming the only name is a last name.
        msg ='Malformed name, EOSC expects one first name and one last name: "%s" ("%s")' % (name, val)
        collected_messages.append(msg)
        return '', val

    else:
        # TODO: Wild guess: Just returning the whole thing as last name. I could also just return the last item as last name.
        msg ='Malformed name, EOSC expects one first name and one last name: "%s" ("%s")' % (name, val)
        collected_messages.append(msg)
        return '', val
    


###########################
### Metadata extraction ###
###########################

def extract_bluecloud_metadata(md):

    collected_messages = []

    global ORDER_TYPES
    #if ORDER_TYPES is None:
    #    LOGGER.info('Retrieving controlled vocabularies...')
    #    ORDER_TYPES = cv_retrieve.get_cv_values('ORDER_TYPE')
    #    cv_retrieve.print_cv('ORDER_TYPES', ORDER_TYPES, LOGGER.debug)
    #    print('****************ORDER_TYPES************')
    #    print(ORDER_TYPES)
    ORDER_TYPES = {'fully open access': 'order_type-fully_open_access', 'open access': 'order_type-open_access', 'order required': 'order_type-order_required', 'other': 'order_type-other'}

    global FUNDING_BODIES
    #if FUNDING_BODIES is None:
    #    FUNDING_BODIES = cv_retrieve.get_cv_values('FUNDING_BODY')
    #    print('****************FUNDING_BODIES************')
    #    print(FUNDING_BODIES)
    FUNDING_BODIES = {'agency for environment and energy management (ademe)': 'funding_body-ademe', 'arts and humanities research council (ahrc)': 'funding_body-ahrc', 'academy of finland (aka)': 'funding_body-aka', 'national authority for scientific research (ancs)': 'funding_body-ancs', 'french national research agency (anr)': 'funding_body-anr', 'research and development agency (apvv)': 'funding_body-apvv', 'australian research council (arc)': 'funding_body-arc', 'slovenian research agency (arrs)': 'funding_body-arrs', 'alfred wegener institute for polar and marine research (awi)': 'funding_body-awi', 'biotechnology and biological sciences research council (bbsrc)': 'funding_body-bbsrc', 'belmont forum (bf)': 'funding_body-bf', 'federal ministry of education and research (bmbf)': 'funding_body-bmbf', 'la caixa foundation (caixa)': 'funding_body-caixa', 'center for industrial technological development (cdti)': 'funding_body-cdti', 'alternative energies and atomic energy commission (cea)': 'funding_body-cea', 'canadian institutes of health research (cihr)': 'funding_body-cihr', 'national university research council (cncsis) - romania': 'funding_body-cncsis', 'national centre for space studies (cnes)': 'funding_body-cnes', 'national council for scientific and technological development (cnpq)': 'funding_body-cnpq', 'national research council (cnr)': 'funding_body-cnr', 'national centre for scientific research (cnrs)': 'funding_body-cnrs', 'croatian science foundation (csf)': 'funding_body-csf', 'spanish national research council (csic)': 'funding_body-csic', 'danish agency for science and higher education (dashe)': 'funding_body-dashe', 'danish agency for science, technology and innovation (dasti)': 'funding_body-dasti', 'the danish council for independent research (ddf)': 'funding_body-ddf', 'danish council for independent research (dff)': 'funding_body-dff', 'german research foundation (dfg)': 'funding_body-dfg', 'general operational directorate for economy, employment and research (dgo6)': 'funding_body-dgo6', 'german aerospace center (dlr)': 'funding_body-dlr', 'danish national research foundation (dnrf)': 'funding_body-dnrf', 'federal department of economic affairs, education and research (eaer)': 'funding_body-eaer', 'european comission (ec)': 'funding_body-ec', 'engineering and physical sciences research council (epsrc)': 'funding_body-epsrc', 'european space agency (esa)': 'funding_body-esa', 'economic and social research council (esrc)': 'funding_body-esrc', 'estonian research council (etag)': 'funding_body-etag', 'são paulo research foundation (fapesp)': 'funding_body-fapesp', 'foundation for science and technology (fct)': 'funding_body-fct', 'austrian research promotion agency (ffg)': 'funding_body-ffg', 'foundation for polish science (fnp)': 'funding_body-fnp', 'national research fund (fnr)': 'funding_body-fnr', 'fonds national de la recherche scientifique (fnrs)': 'funding_body-fnrs', 'foundation for fundamental research on matter (fom)': 'funding_body-fom', 'swedish research council for health, working life and welfare (forte)': 'funding_body-forte', 'fritz thyssen foundation (fts)': 'funding_body-fts', 'austrian science fund (fwf)': 'funding_body-fwf', 'research foundation flanders (fwo)': 'funding_body-fwo', 'czech science foundation (gacr)': 'funding_body-gacr', 'general secretariat for research and technology (gsrt)': 'funding_body-gsrt', 'innovation fund denmark (ifd)': 'funding_body-ifd', 'french research institute for exploitation of the sea (ifremer)': 'funding_body-ifremer', 'innovation fund of the ministry of economy of the slovak republic (imsr)': 'funding_body-imsr', 'brussels institute for research and innovation (innoviris)': 'funding_body-innoviris', 'national institute of agricultural research (inra)': 'funding_body-inra', 'national institute of health and medical research (inserm)': 'funding_body-inserm', 'french polar institute (ipev)': 'funding_body-ipev', 'irish research council (irc)': 'funding_body-irc', 'international science council (isc)': 'funding_body-isc', 'carlos iii health institute (isciii)': 'funding_body-isciii', 'israel science foundation (isf)': 'funding_body-isf', 'agency for innovation by science and technology (iwt)': 'funding_body-iwt', 'japanese society for the promotion of science (jsps)': 'funding_body-jsps', 'japanese science and technology agency (jst)': 'funding_body-jst', 'knut and alice wallenberg foundation (kaws)': 'funding_body-kaws', 'knowledge foundation (kks)': 'funding_body-kks', 'research council of lithuania (lmt)': 'funding_body-lmt', 'malta council for science and technology (mcst)': 'funding_body-mcst', 'ministry for education and scientific research (mecr)': 'funding_body-mecr', 'ministry of higher education and research (mesr)': 'funding_body-mesr', 'ministry of education, science and technological development of republic of serbia (mestd)': 'funding_body-mestd', 'ministry for economic development and technology (mgrt)': 'funding_body-mgrt', 'ministry for economy and competitveness (mineco)': 'funding_body-mineco', 'swedish foundation for strategic environmental research (mistra)': 'funding_body-mistra', 'agency for science, innovation and technology (mita)': 'funding_body-mita', 'ministry for education, university and research (miur)': 'funding_body-miur', "ministry of science and technology of the people's republic of china (most)": 'funding_body-most', 'max planck society for the advancement of science (mpg)': 'funding_body-mpg', 'medical research council (mrc)': 'funding_body-mrc', 'ministry of science and education republic of croatia (mse)': 'funding_body-mse', 'the ministry of education, science, research and sports of the slovak republic (msvvas sr)': 'funding_body-msvvas_sr', 'national aeronautics and space administration (nasa)': 'funding_body-nasa', 'national centre for research and development (ncbir)': 'funding_body-ncbir', 'national science center (ncn)': 'funding_body-ncn', 'natural environment research council (nerc)': 'funding_body-nerc', 'national health and medical research council (nhmrc)': 'funding_body-nhmrc', 'national institutes of health (nig)': 'funding_body-nig', 'national research, development and innovation fund (nkfia)': 'funding_body-nkfia', 'national research foundation (nrf)': 'funding_body-nrf', 'natural sciences and engineering research council of canada (nserc)': 'funding_body-nserc', 'national science foundation (nsf)': 'funding_body-nsf', 'netherlands organisation for scientific research (nwo)': 'funding_body-nwo', 'austrian academy of sciences (oeaw)': 'funding_body-oeaw', 'national foundation for research, technology and development (oenfte)': 'funding_body-oenfte', 'french national aerospace research center (onera)': 'funding_body-onera', 'other': 'funding_body-other', 'icelandic centre for research (rannis)': 'funding_body-rannis', 'research council of norway (rcn)': 'funding_body-rcn', 'research council uk (rcuk)': 'funding_body-rcuk', 'the swedish foundation for humanities and social sciences (rj)': 'funding_body-rj', 'research promotion foundation (rpf)': 'funding_body-rpf', 'swedish energy agency (sea)': 'funding_body-sea', 'swedish environmental protection agency (sepa)': 'funding_body-sepa', 'science foundation ireland (sfi)': 'funding_body-sfi', 'secretariat-general for investment (sgpi)': 'funding_body-sgpi', 'swiss national science foundation (snf)': 'funding_body-snf', 'swedish national space board (snsb)': 'funding_body-snsb', 'swedish reseach council formas (srcf)': 'funding_body-srcf', 'swedish radiation safety authority (srsa)': 'funding_body-srsa', 'swedish foundation for strategic research (ssf)': 'funding_body-ssf', 'social sciences and humanities research council (sshrc)': 'funding_body-sshrc', 'science and technology facilities council (stfc)': 'funding_body-stfc', 'technology foundation (stw)': 'funding_body-stw', 'technology agency of the czech republic (tacr)': 'funding_body-tacr', 'tara expeditions foundation (tara)': 'funding_body-tara', 'finnish funding agency for technology and innovation (tekes)': 'funding_body-tekes', 'scientific and technological research council of turkey (tubitak)': 'funding_body-tubitak', 'executive agency for higher education, research, development and innovation funding (uefiscdi - cncs)': 'funding_body-uefiscdi_cncs', 'uk research and innovation (ukri)': 'funding_body-ukri', 'scientific grant agency (vega)': 'funding_body-vega', 'state education development agency (viaa)': 'funding_body-viaa', 'swedish governmental agency for innovation systems (vinnova)': 'funding_body-vinnova', 'flanders innovation & entrepeneurship (vlaio)': 'funding_body-vlaio', 'swedish research council (vr)': 'funding_body-vr', 'volkswagen foundation (vs)': 'funding_body-vs', 'wellcome trust (wt)': 'funding_body-wt', 'vienna science and technology fund (wwtf)': 'funding_body-wwtf'}

    global FUNDING_PROGRAMS
    #if FUNDING_PROGRAMS is None:
    #    FUNDING_PROGRAMS = cv_retrieve.get_cv_values('FUNDING_PROGRAM')
    #    print('****************FUNDING_PROGRAMS************')
    #    print(FUNDING_PROGRAMS)
    FUNDING_PROGRAMS = {'anti fraud information system (afis2020)': 'funding_program-afis2020', 'european agricultural guarantee fund (after transfers between eagf and eafrd) (agr)': 'funding_program-agr', 'net transfer between eagf and eafrd (agrnet)': 'funding_program-agrnet', 'asylum, migration and integration fund (amf)': 'funding_program-amf', 'rights, equality and citizenship programme (cdf2020)': 'funding_program-cdf2020', 'connecting europe facility (cef)': 'funding_program-cef', 'cohesion fund (cf)': 'funding_program-cf', 'contribution from the cohesion fund to the cef programme (cf_det)': 'funding_program-cf_det', 'common foreign and security policy (cfsp2020)': 'funding_program-cfsp', 'europe for citizens (cit2020)': 'funding_program-cit2020', 'competitiveness (more developed regions) (compreg)': 'funding_program-compreg', 'consumer programme (cons)': 'funding_program-cons', 'european earth observation programme (copernicus)': 'funding_program-copernicus', 'programme for the competitiveness of enterprises and small and medium-sized enterprises (cosme)': 'funding_program-cosme', 'union civil protection mechanism — member states (cpm_h3)': 'funding_program-cpm_h3', 'union civil protection mechanism — outside eu (cpm_h4)': 'funding_program-cpm_h4', 'creative europe programme (crea)': 'funding_program-crea', 'action programme for customs in the european union (cust 2020)': 'funding_program-cust2020', 'development cooperation instrument (dci2020)': 'funding_program-dci2020', 'the union programme for education, training, youth and sport (erasmus+) (e4a)': 'funding_program-e4a', 'european agricultural fund for rural development (after transfers between eagf and eafrd) (eafrd)': 'funding_program-eafrd', 'european agricultural fund for rural development (eafrd2020)': 'funding_program-eafrd2020', 'european agricultural guarantee fund (eagf2020)': 'funding_program-eagf2020', 'emergency aid reserve (ear2020)': 'funding_program-ear2020', 'energy projects to aid economic recovery (eerp)': 'funding_program-eerp', 'european fund for sustainable development (efsd)': 'funding_program-efsd', 'european fund for strategic investments (efsi)': 'funding_program-efsi', 'european globalisation adjustment fund (egf2020)': 'funding_program-egf2020', 'european instrument for democracy and human rights (eidhr2020)': 'funding_program-eidhr2020', 'european maritime and fisheries fund (emff2020)': 'funding_program-emff2020', 'european neighbourhood instrument (eni)': 'funding_program-eni', 'european regional development fund (erdf)': 'funding_program-erdf', 'european solidarity corps (esc)': 'funding_program-esc', 'european social fund (esf)': 'funding_program-esf', 'european statistical programme (esp2017)': 'funding_program-esp2017', 'european statistical programme (esp2020)': 'funding_program-esp2020', 'eu aid volunteers initiative (euav)': 'funding_program-euav', 'euratom research and training programme (euratom)': 'funding_program-euratom', 'comparison of fingerprints for the effective application of the dublin convention (eurodac2020)': 'funding_program-eurodac2020', 'european union solidarity fund (eusf2020)': 'funding_program-eusf2020', 'european union solidarity fund (eusf) — member states (eusf_h3)': 'funding_program-eusf_h3', 'european union solidarity fund (eusf) — countries negotiating for accession (eusf_h4)': 'funding_program-eusf_h4', 'fund for european aid to the most deprived (fead)': 'funding_program-fead', 'food and feed (ff2020)': 'funding_program-ff2020', 'specific activities in the field of financial reporting and auditing (finser2020)': 'funding_program-finser2020', 'action programme for taxation in the european union (fisc2020)': 'funding_program-fisc2020', 'implementation and exploitation of european satellite navigation systems (egnos and galileo) (gal2014)': 'funding_program-gal2014', 'eu cooperation with greenland (grld2020)': 'funding_program-grld2020', 'the framework programme for research and innovation (h2020)': 'funding_program-h2020', "union's action in the field of health (health programme) (health)": 'funding_program-health', "programme to promote activities in the field of the protection of the european union's financial interests (herc3)": 'funding_program-herc3', 'supplementary high flux reactor (hfr) programmes (hfr2015)': 'funding_program-hfr2015', 'humanitarian aid (huma2020)': 'funding_program-huma2020', 'enhancing consumers involvement in eu policy making in the field of financial services (icfs)': 'funding_program-icfs', 'instrument for emergency support within the union (ies)': 'funding_program-ies', 'instrument contributing to stability and peace (ifs2020)': 'funding_program-ifs2020', 'instrument for nuclear safety cooperation (insc2020)': 'funding_program-insc2020', 'instrument for pre-accession assistance (ipa2)': 'funding_program-ipa2', 'interoperability solutions for european public administrations (isa2015)': 'funding_program-isa2015', 'interoperability solutions for european public administrations, businesses and citizens (isa2020)': 'funding_program-isa2020', 'internal security fund (isf)': 'funding_program-isf', 'international thermonuclear experimental reactor (iter)': 'funding_program-iter', 'justice programme (just)': 'funding_program-just', 'programme for the environment and climate action (life2020)': 'funding_program-life2020', 'guarantee fund for external actions (loan2020)': 'funding_program-loan2020', 'macro financial assistance (mfa)': 'funding_program-mfa', 'nuclear decommissioning assistance programmes in bulgaria, lithuania and slovakia (nd)': 'funding_program-nd', 'other': 'funding_program-other', 'outermost and sparsely populated regions (outreg)': 'funding_program-outreg', 'exchange, assistance and training programme for the protection of the euro against counterfeiting (peri2020)': 'funding_program-peri2020', 'partnership instrument for cooperation with third countries (pi)': 'funding_program-pi', 'european union programme for employment and social innovation (psci)': 'funding_program-psci', 'regional convergence (regconv)': 'funding_program-regconv', 'compulsory contributions to regional fisheries management organisations (rfmos) and to other international organisations': 'funding_program-rfmos', 'sustainable fisheries partnership agreements (sfpas)': 'funding_program-sfpas', 'schengen information system (sis2020)': 'funding_program-sis2020', 'technical assistance and innovative actions (ta_ia)': 'funding_program-ta_ia', 'instrument of financial support for encouraging the economic development of the turkish cypriot community (tcc)': 'funding_program-tcc', 'european territorial cooperation (terrcoop)': 'funding_program-terrcoop', 'transition regions (transreg)': 'funding_program-transreg', 'visa information system (vis2020)': 'funding_program-vis2020', 'youth employment initiative (specific top-up allocation) (yei))': 'funding_program-yei'}

    global CV_DOM, CV_SUBDOM, CV_DOM_MAPPING
    #if CV_DOM is None:
    #    CV_DOM, CV_SUBDOM, CV_DOM_MAPPING = cv_retrieve.get_values_and_subvalues2('SCIENTIFIC_DOMAIN', 'SCIENTIFIC_SUBDOMAIN')
    #    print('****************CV_DOM************')
    #    print(CV_DOM)
    #    print('****************CV_SUBDOM************')
    #    print(CV_SUBDOM)
    #    print('****************CV_DOM_MAPPING************')
    #    print(CV_DOM_MAPPING)
    CV_DOM = {'agricultural sciences': 'scientific_domain-agricultural_sciences', 'engineering & technology': 'scientific_domain-engineering_and_technology', 'generic': 'scientific_domain-generic', 'humanities': 'scientific_domain-humanities', 'medical & health sciences': 'scientific_domain-medical_and_health_sciences', 'natural sciences': 'scientific_domain-natural_sciences', 'other': 'scientific_domain-other', 'social sciences': 'scientific_domain-social_sciences'}
    CV_SUBDOM = {'agricultural sciences.agricultural biotechnology': 'scientific_subdomain-agricultural_sciences-agricultural_biotechnology', 'agricultural sciences.agriculture, forestry & fisheries': 'scientific_subdomain-agricultural_sciences-agriculture_forestry_and_fisheries', 'agricultural sciences.animal & dairy sciences': 'scientific_subdomain-agricultural_sciences-animal_and_dairy_sciences', 'agricultural sciences.other agricultural sciences': 'scientific_subdomain-agricultural_sciences-other_agricultural_sciences', 'agricultural sciences.veterinary sciences': 'scientific_subdomain-agricultural_sciences-veterinary_sciences', 'engineering & technology.chemical engineering': 'scientific_subdomain-engineering_and_technology-chemical_engineering', 'engineering & technology.civil engineering': 'scientific_subdomain-engineering_and_technology-civil_engineering', 'engineering & technology.electrical, electronic & information engineering': 'scientific_subdomain-engineering_and_technology-electrical_electronic_and_information_engineering', 'engineering & technology.environmental biotechnology': 'scientific_subdomain-engineering_and_technology-environmental_biotechnology', 'engineering & technology.environmental engineering': 'scientific_subdomain-engineering_and_technology-environmental_engineering', 'engineering & technology.industrial biotechnology': 'scientific_subdomain-engineering_and_technology-industrial_biotechnology', 'engineering & technology.materials engineering': 'scientific_subdomain-engineering_and_technology-materials_engineering', 'engineering & technology.mechanical engineering': 'scientific_subdomain-engineering_and_technology-mechanical_engineering', 'engineering & technology.medical engineering': 'scientific_subdomain-engineering_and_technology-medical_engineering', 'engineering & technology.nanotechnology': 'scientific_subdomain-engineering_and_technology-nanotechnology', 'engineering & technology.other engineering & technology sciences': 'scientific_subdomain-engineering_and_technology-other_engineering_and_technology_sciences', 'generic.generic': 'scientific_subdomain-generic-generic', 'humanities.arts': 'scientific_subdomain-humanities-arts', 'humanities.history & archaeology': 'scientific_subdomain-humanities-history_and_archaeology', 'humanities.languages & literature': 'scientific_subdomain-humanities-languages_and_literature', 'humanities.other humanities': 'scientific_subdomain-humanities-other_humanities', 'humanities.philosophy, ethics & religion': 'scientific_subdomain-humanities-philosophy_ethics_and_religion', 'medical & health sciences.basic medicine': 'scientific_subdomain-medical_and_health_sciences-basic_medicine', 'medical & health sciences.clinical medicine': 'scientific_subdomain-medical_and_health_sciences-clinical_medicine', 'medical & health sciences.health sciences': 'scientific_subdomain-medical_and_health_sciences-health_sciences', 'medical & health sciences.medical biotechnology': 'scientific_subdomain-medical_and_health_sciences-medical_biotechnology', 'medical & health sciences.other medical sciences': 'scientific_subdomain-medical_and_health_sciences-other_medical_sciences', 'natural sciences.biological sciences': 'scientific_subdomain-natural_sciences-biological_sciences', 'natural sciences.chemical sciences': 'scientific_subdomain-natural_sciences-chemical_sciences', 'natural sciences.computer & information sciences': 'scientific_subdomain-natural_sciences-computer_and_information_sciences', 'natural sciences.earth & related environmental sciences': 'scientific_subdomain-natural_sciences-earth_and_related_environmental_sciences', 'natural sciences.mathematics': 'scientific_subdomain-natural_sciences-mathematics', 'natural sciences.other natural sciences': 'scientific_subdomain-natural_sciences-other_natural_sciences', 'natural sciences.physical sciences': 'scientific_subdomain-natural_sciences-physical_sciences', 'other.other': 'scientific_subdomain-other-other', 'social sciences.economics & business': 'scientific_subdomain-social_sciences-economics_and_business', 'social sciences.educational sciences': 'scientific_subdomain-social_sciences-educational_sciences', 'social sciences.law': 'scientific_subdomain-social_sciences-law', 'social sciences.media & communications': 'scientific_subdomain-social_sciences-media_and_communications', 'social sciences.other social sciences': 'scientific_subdomain-social_sciences-other_social_sciences', 'social sciences.political sciences': 'scientific_subdomain-social_sciences-political_sciences', 'social sciences.psychology': 'scientific_subdomain-social_sciences-psychology', 'social sciences.social & economic geography': 'scientific_subdomain-social_sciences-social_and_economic_geography', 'social sciences.sociology': 'scientific_subdomain-social_sciences-sociology'}
    CV_DOM_MAPPING = {'scientific_subdomain-agricultural_sciences-agricultural_biotechnology': 'scientific_domain-agricultural_sciences', 'scientific_subdomain-agricultural_sciences-agriculture_forestry_and_fisheries': 'scientific_domain-agricultural_sciences', 'scientific_subdomain-agricultural_sciences-animal_and_dairy_sciences': 'scientific_domain-agricultural_sciences', 'scientific_subdomain-agricultural_sciences-other_agricultural_sciences': 'scientific_domain-agricultural_sciences', 'scientific_subdomain-agricultural_sciences-veterinary_sciences': 'scientific_domain-agricultural_sciences', 'scientific_subdomain-engineering_and_technology-chemical_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-civil_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-electrical_electronic_and_information_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-environmental_biotechnology': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-environmental_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-industrial_biotechnology': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-materials_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-mechanical_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-medical_engineering': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-nanotechnology': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-engineering_and_technology-other_engineering_and_technology_sciences': 'scientific_domain-engineering_and_technology', 'scientific_subdomain-generic-generic': 'scientific_domain-generic', 'scientific_subdomain-humanities-arts': 'scientific_domain-humanities', 'scientific_subdomain-humanities-history_and_archaeology': 'scientific_domain-humanities', 'scientific_subdomain-humanities-languages_and_literature': 'scientific_domain-humanities', 'scientific_subdomain-humanities-other_humanities': 'scientific_domain-humanities', 'scientific_subdomain-humanities-philosophy_ethics_and_religion': 'scientific_domain-humanities', 'scientific_subdomain-medical_and_health_sciences-basic_medicine': 'scientific_domain-medical_and_health_sciences', 'scientific_subdomain-medical_and_health_sciences-clinical_medicine': 'scientific_domain-medical_and_health_sciences', 'scientific_subdomain-medical_and_health_sciences-health_sciences': 'scientific_domain-medical_and_health_sciences', 'scientific_subdomain-medical_and_health_sciences-medical_biotechnology': 'scientific_domain-medical_and_health_sciences', 'scientific_subdomain-medical_and_health_sciences-other_medical_sciences': 'scientific_domain-medical_and_health_sciences', 'scientific_subdomain-natural_sciences-biological_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-chemical_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-computer_and_information_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-earth_and_related_environmental_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-mathematics': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-other_natural_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-natural_sciences-physical_sciences': 'scientific_domain-natural_sciences', 'scientific_subdomain-other-other': 'scientific_domain-other', 'scientific_subdomain-social_sciences-economics_and_business': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-educational_sciences': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-law': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-media_and_communications': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-other_social_sciences': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-political_sciences': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-psychology': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-social_and_economic_geography': 'scientific_domain-social_sciences', 'scientific_subdomain-social_sciences-sociology': 'scientific_domain-social_sciences'}

    global CV_CAT, CV_SUBCAT, CV_CAT_MAPPING
    #if CV_CAT is None:
    #    CV_CAT, CV_SUBCAT, CV_CAT_MAPPING = cv_retrieve.get_values_and_subvalues2('CATEGORY', 'SUBCATEGORY')
    #    print('****************CV_CAT************')
    #    print(CV_CAT)
    #    print('****************CV_SUBCAT************')
    #    print(CV_SUBCAT)
    #    print('****************CV_CAT_MAPPING************')
    #    print(CV_CAT_MAPPING)
    CV_CAT = {'compute': 'category-access_physical_and_eInfrastructures-compute', 'data storage': 'category-access_physical_and_eInfrastructures-data_storage', 'instrument & equipment': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'material storage': 'category-access_physical_and_eInfrastructures-material_storage', 'network': 'category-access_physical_and_eInfrastructures-network', 'aggregators & integrators': 'category-aggregators_and_integrators-aggregators_and_integrators', 'other': 'category-other-other', 'data analysis': 'category-processing_and_analysis-data_analysis', 'data management': 'category-processing_and_analysis-data_management', 'measurement & materials analysis': 'category-processing_and_analysis-measurement_and_materials_analysis', 'operations & infrastructure management services': 'category-security_and_operations-operations_and_infrastructure_management_services', 'security & identity': 'category-security_and_operations-security_and_identity', 'applications': 'category-sharing_and_discovery-applications', 'data': 'category-sharing_and_discovery-data', 'development resources': 'category-sharing_and_discovery-development_resources', 'samples': 'category-sharing_and_discovery-samples', 'scholarly communication': 'category-sharing_and_discovery-scholarly_communication', 'software': 'category-sharing_and_discovery-software', 'consultancy & support': 'category-training_and_support-consultancy_and_support', 'education & training': 'category-training_and_support-education_and_training'}
    CV_SUBCAT = {'compute.container management': 'subcategory-access_physical_and_eInfrastructures-compute-container_management', 'compute.job execution': 'subcategory-access_physical_and_eInfrastructures-compute-job_execution', 'compute.orchestration': 'subcategory-access_physical_and_eInfrastructures-compute-orchestration', 'compute.other': 'subcategory-access_physical_and_eInfrastructures-compute-other', 'compute.serverless applications repository': 'subcategory-access_physical_and_eInfrastructures-compute-serverless_applications_repository', 'compute.virtual machine management': 'subcategory-access_physical_and_eInfrastructures-compute-virtual_machine_management', 'compute.workload management': 'subcategory-access_physical_and_eInfrastructures-compute-workload_management', 'data storage.archive': 'subcategory-access_physical_and_eInfrastructures-data_storage-archive', 'data storage.backup': 'subcategory-access_physical_and_eInfrastructures-data_storage-backup', 'data storage.data': 'subcategory-access_physical_and_eInfrastructures-data_storage-data', 'data storage.digital preservation': 'subcategory-access_physical_and_eInfrastructures-data_storage-digital_preservation', 'data storage.disk': 'subcategory-access_physical_and_eInfrastructures-data_storage-disk', 'data storage.file': 'subcategory-access_physical_and_eInfrastructures-data_storage-file', 'data storage.online': 'subcategory-access_physical_and_eInfrastructures-data_storage-online', 'data storage.other': 'subcategory-access_physical_and_eInfrastructures-data_storage-other', 'data storage.queue': 'subcategory-access_physical_and_eInfrastructures-data_storage-queue', 'data storage.recovery': 'subcategory-access_physical_and_eInfrastructures-data_storage-recovery', 'data storage.replicated': 'subcategory-access_physical_and_eInfrastructures-data_storage-replicated', 'data storage.synchronised': 'subcategory-access_physical_and_eInfrastructures-data_storage-synchronised', 'instrument & equipment.chromatographer': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-chromatographer', 'instrument & equipment.cytometer': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-cytometer', 'instrument & equipment.digitisation equipment': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-digitisation_equipment', 'instrument & equipment.geophysical': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-geophysical', 'instrument & equipment.laser': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-laser', 'instrument & equipment.microscopy': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-microscopy', 'instrument & equipment.monument maintenance equipment': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-monument_maintenance_equipment', 'instrument & equipment.other': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-other', 'instrument & equipment.radiation': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-radiation', 'instrument & equipment.spectrometer': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-spectrometer', 'instrument & equipment.spectrophotometer': 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-spectrophotometer', 'material storage.archiving': 'subcategory-access_physical_and_eInfrastructures-material_storage-archiving', 'material storage.assembly': 'subcategory-access_physical_and_eInfrastructures-material_storage-assembly', 'material storage.disposal': 'subcategory-access_physical_and_eInfrastructures-material_storage-disposal', 'material storage.fulfilment': 'subcategory-access_physical_and_eInfrastructures-material_storage-fulfilment', 'material storage.other': 'subcategory-access_physical_and_eInfrastructures-material_storage-other', 'material storage.packaging': 'subcategory-access_physical_and_eInfrastructures-material_storage-packaging', 'material storage.preservation': 'subcategory-access_physical_and_eInfrastructures-material_storage-preservation', 'material storage.quality inspecting': 'subcategory-access_physical_and_eInfrastructures-material_storage-quality_inspecting', 'material storage.repository': 'subcategory-access_physical_and_eInfrastructures-material_storage-repository', 'material storage.reworking': 'subcategory-access_physical_and_eInfrastructures-material_storage-reworking', 'material storage.sorting': 'subcategory-access_physical_and_eInfrastructures-material_storage-sorting', 'material storage.warehousing': 'subcategory-access_physical_and_eInfrastructures-material_storage-warehousing', 'network.content delivery network': 'subcategory-access_physical_and_eInfrastructures-network-content_delivery_network', 'network.direct connect': 'subcategory-access_physical_and_eInfrastructures-network-direct_connect', 'network.exchange': 'subcategory-access_physical_and_eInfrastructures-network-exchange', 'network.load balancer': 'subcategory-access_physical_and_eInfrastructures-network-load_balancer', 'network.other': 'subcategory-access_physical_and_eInfrastructures-network-other', 'network.traffic manager': 'subcategory-access_physical_and_eInfrastructures-network-traffic_manager', 'network.virtual network': 'subcategory-access_physical_and_eInfrastructures-network-virtual_nework', 'network.vpn gateway': 'subcategory-access_physical_and_eInfrastructures-network-vpn_gateway', 'aggregators & integrators.applications': 'subcategory-aggregators_and_integrators-aggregators_and_integrators-applications', 'aggregators & integrators.data': 'subcategory-aggregators_and_integrators-aggregators_and_integrators-data', 'aggregators & integrators.other': 'subcategory-aggregators_and_integrators-aggregators_and_integrators-other', 'aggregators & integrators.services': 'subcategory-aggregators_and_integrators-aggregators_and_integrators-services', 'aggregators & integrators.software': 'subcategory-aggregators_and_integrators-aggregators_and_integrators-software', 'other.other': 'subcategory-other-other-other', 'data analysis.2d/3d digitisation': 'subcategory-processing_and_analysis-data_analysis-2d_3d_digitisation', 'data analysis.artificial intelligence': 'subcategory-processing_and_analysis-data_analysis-artificial_intelligence', 'data analysis.data exploitation': 'subcategory-processing_and_analysis-data_analysis-data_exploitation', 'data analysis.forecast': 'subcategory-processing_and_analysis-data_analysis-forecast', 'data analysis.image/data analysis': 'subcategory-processing_and_analysis-data_analysis-image_data_analysis', 'data analysis.machine learning': 'subcategory-processing_and_analysis-data_analysis-machine_learning', 'data analysis.other': 'subcategory-processing_and_analysis-data_analysis-other', 'data analysis.visualization': 'subcategory-processing_and_analysis-data_analysis-visualization', 'data analysis.workflows': 'subcategory-processing_and_analysis-data_analysis-workflows', 'data management.access': 'subcategory-processing_and_analysis-data_management-access', 'data management.annotation': 'subcategory-processing_and_analysis-data_management-annotation', 'data management.anonymisation': 'subcategory-processing_and_analysis-data_management-anonymisation', 'data management.brokering': 'subcategory-processing_and_analysis-data_management-brokering', 'data management.digitisation': 'subcategory-processing_and_analysis-data_management-digitisation', 'data management.discovery': 'subcategory-processing_and_analysis-data_management-discovery', 'data management.embargo': 'subcategory-processing_and_analysis-data_management-embargo', 'data management.interlinking': 'subcategory-processing_and_analysis-data_management-interlinking', 'data management.maintenance': 'subcategory-processing_and_analysis-data_management-maintenance', 'data management.mining': 'subcategory-processing_and_analysis-data_management-mining', 'data management.other': 'subcategory-processing_and_analysis-data_management-other', 'data management.persistent identifier': 'subcategory-processing_and_analysis-data_management-persistent_identifier', 'data management.preservation': 'subcategory-processing_and_analysis-data_management-preservation', 'data management.processing_and_analysis-data_management-publishing': 'subcategory-processing_and_analysis-data_management-publishing', 'data management.registration': 'subcategory-processing_and_analysis-data_management-registration', 'data management.transfer': 'subcategory-processing_and_analysis-data_management-transfer', 'data management.validation': 'subcategory-processing_and_analysis-data_management-validation', 'measurement & materials analysis.analysis': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-analysis', 'measurement & materials analysis.characterisation': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-characterisation', 'measurement & materials analysis.maintenance & modification': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-maintenance_and_modification', 'measurement & materials analysis.other': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-other', 'measurement & materials analysis.production': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-production', 'measurement & materials analysis.testing & validation': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-testing_and_validation', 'measurement & materials analysis.validation': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-validation', 'measurement & materials analysis.workflows': 'subcategory-processing_and_analysis-measurement_and_materials_analysis-workflows', 'operations & infrastructure management services.accounting': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-accounting', 'operations & infrastructure management services.analysis': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-analysis', 'operations & infrastructure management services.billing': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-billing', 'operations & infrastructure management services.configuration': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-configuration', 'operations & infrastructure management services.coordination': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-coordination', 'operations & infrastructure management services.helpdesk': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-helpdesk', 'operations & infrastructure management services.monitoring': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-monitoring', 'operations & infrastructure management services.order management': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-order_management', 'operations & infrastructure management services.other': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-other', 'operations & infrastructure management services.transportation': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-transportation', 'operations & infrastructure management services.utilities': 'subcategory-security_and_operations-operations_and_infrastructure_management_services-utilities', 'security & identity.certification authority': 'subcategory-security_and_operations-security_and_identity-certification_authority', 'security & identity.coordination': 'subcategory-security_and_operations-security_and_identity-coordination', 'security & identity.firewall': 'subcategory-security_and_operations-security_and_identity-firewall', 'security & identity.group management': 'subcategory-security_and_operations-security_and_identity-group_management', 'security & identity.identity & access management': 'subcategory-security_and_operations-security_and_identity-identity_and_access_management', 'security & identity.other': 'subcategory-security_and_operations-security_and_identity-other', 'security & identity.single sign-on': 'subcategory-security_and_operations-security_and_identity-single_sign_on', 'security & identity.threat protection': 'subcategory-security_and_operations-security_and_identity-threat_protection', 'security & identity.tools': 'subcategory-security_and_operations-security_and_identity-tools', 'security & identity.user authentication': 'subcategory-security_and_operations-security_and_identity-user_authentication', 'applications.applications repository': 'subcategory-sharing_and_discovery-applications-applications_repository', 'applications.business': 'subcategory-sharing_and_discovery-applications-business', 'applications.collaboration': 'subcategory-sharing_and_discovery-applications-collaboration', 'applications.communication': 'subcategory-sharing_and_discovery-applications-communication', 'applications.education': 'subcategory-sharing_and_discovery-applications-education', 'applications.other': 'subcategory-sharing_and_discovery-applications-other', 'applications.productivity': 'subcategory-sharing_and_discovery-applications-productivity', 'applications.social/networking': 'subcategory-sharing_and_discovery-applications-social_networking', 'applications.utilities': 'subcategory-sharing_and_discovery-applications-utilities', 'data.clinical trial data': 'subcategory-sharing_and_discovery-data-clinical_trial_data', 'data.data archives': 'subcategory-sharing_and_discovery-data-data_archives', 'data.epidemiological data': 'subcategory-sharing_and_discovery-data-epidemiological_data', 'data.government & agency data': 'subcategory-sharing_and_discovery-data-government_and_agency_data', 'data.online service data': 'subcategory-sharing_and_discovery-data-online_service_data', 'data.other': 'subcategory-sharing_and_discovery-data-other', 'data.scientific/research data': 'subcategory-sharing_and_discovery-data-scientific_research_data', 'data.statistical data': 'subcategory-sharing_and_discovery-data-statistical_data', 'development resources.apis repository/gateway': 'subcategory-sharing_and_discovery-development_resources-apis_repository_gateway', 'development resources.developer tools': 'subcategory-sharing_and_discovery-development_resources-developer_tools', 'development resources.other': 'subcategory-sharing_and_discovery-development_resources-other', 'development resources.software development kits': 'subcategory-sharing_and_discovery-development_resources-software_development_kits', 'development resources.software libraries': 'subcategory-sharing_and_discovery-development_resources-software_libraries', 'samples.biological samples': 'subcategory-sharing_and_discovery-samples-biological_samples', 'samples.characterisation': 'subcategory-sharing_and_discovery-samples-characterisation', 'samples.chemical compounds library': 'subcategory-sharing_and_discovery-samples-chemical_compounds_library', 'samples.other': 'subcategory-sharing_and_discovery-samples-other', 'samples.preparation': 'subcategory-sharing_and_discovery-samples-preparation', 'scholarly communication.analysis': 'subcategory-sharing_and_discovery-scholarly_communication-analysis', 'scholarly communication.assessment': 'subcategory-sharing_and_discovery-scholarly_communication-assessment', 'scholarly communication.discovery': 'subcategory-sharing_and_discovery-scholarly_communication-discovery', 'scholarly communication.other': 'subcategory-sharing_and_discovery-scholarly_communication-other', 'scholarly communication.outreach': 'subcategory-sharing_and_discovery-scholarly_communication-outreach', 'scholarly communication.preparation': 'subcategory-sharing_and_discovery-scholarly_communication-preparation', 'scholarly communication.publication': 'subcategory-sharing_and_discovery-scholarly_communication-publication', 'scholarly communication.writing': 'subcategory-sharing_and_discovery-scholarly_communication-writing', 'software.libraries': 'subcategory-sharing_and_discovery-software-libraries', 'software.other': 'subcategory-sharing_and_discovery-software-other', 'software.platform': 'subcategory-sharing_and_discovery-software-platform', 'software.software package': 'subcategory-sharing_and_discovery-software-software_package', 'software.software repository': 'subcategory-sharing_and_discovery-software-software_repository', 'consultancy & support.application optimisation': 'subcategory-training_and_support-consultancy_and_support-application_optimisation', 'consultancy & support.application_porting': 'subcategory-training_and_support-consultancy_and_support-application_porting', 'consultancy & support.application scaling': 'subcategory-training_and_support-consultancy_and_support-application_scaling', 'consultancy & support.audit & assessment': 'subcategory-training_and_support-consultancy_and_support-audit_and_assessment', 'consultancy & support.benchmarking': 'subcategory-training_and_support-consultancy_and_support-benchmarking', 'consultancy & support.calibration': 'subcategory-training_and_support-consultancy_and_support-calibration', 'consultancy & support.certification': 'subcategory-training_and_support-consultancy_and_support-certification', 'consultancy & support.consulting': 'subcategory-training_and_support-consultancy_and_support-consulting', 'consultancy & support.methodology development': 'subcategory-training_and_support-consultancy_and_support-methodology_development', 'consultancy & support.modeling & simulation': 'subcategory-training_and_support-consultancy_and_support-modeling_and_simulation', 'consultancy & support.other': 'subcategory-training_and_support-consultancy_and_support-other', 'consultancy & support.prototype development': 'subcategory-training_and_support-consultancy_and_support-prototype_development', 'consultancy & support.software development': 'subcategory-training_and_support-consultancy_and_support-software_development', 'consultancy & support.software improvement': 'subcategory-training_and_support-consultancy_and_support-software_improvement', 'consultancy & support.technology transfer': 'subcategory-training_and_support-consultancy_and_support-technology_transfer', 'consultancy & support.testing': 'subcategory-training_and_support-consultancy_and_support-testing', 'education & training.in-house courses': 'subcategory-training_and_support-education_and_training-in_house_courses', 'education & training.online courses': 'subcategory-training_and_support-education_and_training-online_courses', 'education & training.open registration courses': 'subcategory-training_and_support-education_and_training-open_registration_courses', 'education & training.other': 'subcategory-training_and_support-education_and_training-other', 'education & training.related training': 'subcategory-training_and_support-education_and_training-related_training', 'education & training.required training': 'subcategory-training_and_support-education_and_training-required_training', 'education & training.training platform': 'subcategory-training_and_support-education_and_training-training_platform', 'education & training.training tool': 'subcategory-training_and_support-education_and_training-training_tool'}
    CV_CAT_MAPPING = {'subcategory-access_physical_and_eInfrastructures-compute-container_management': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-job_execution': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-orchestration': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-other': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-serverless_applications_repository': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-virtual_machine_management': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-compute-workload_management': 'category-access_physical_and_eInfrastructures-compute', 'subcategory-access_physical_and_eInfrastructures-data_storage-archive': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-backup': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-data': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-digital_preservation': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-disk': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-file': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-online': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-other': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-queue': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-recovery': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-replicated': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-data_storage-synchronised': 'category-access_physical_and_eInfrastructures-data_storage', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-chromatographer': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-cytometer': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-digitisation_equipment': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-geophysical': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-laser': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-microscopy': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-monument_maintenance_equipment': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-other': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-radiation': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-spectrometer': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-instrument_and_equipment-spectrophotometer': 'category-access_physical_and_eInfrastructures-instrument_and_equipment', 'subcategory-access_physical_and_eInfrastructures-material_storage-archiving': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-assembly': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-disposal': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-fulfilment': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-other': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-packaging': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-preservation': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-quality_inspecting': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-repository': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-reworking': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-sorting': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-material_storage-warehousing': 'category-access_physical_and_eInfrastructures-material_storage', 'subcategory-access_physical_and_eInfrastructures-network-content_delivery_network': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-direct_connect': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-exchange': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-load_balancer': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-other': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-traffic_manager': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-virtual_nework': 'category-access_physical_and_eInfrastructures-network', 'subcategory-access_physical_and_eInfrastructures-network-vpn_gateway': 'category-access_physical_and_eInfrastructures-network', 'subcategory-aggregators_and_integrators-aggregators_and_integrators-applications': 'category-aggregators_and_integrators-aggregators_and_integrators', 'subcategory-aggregators_and_integrators-aggregators_and_integrators-data': 'category-aggregators_and_integrators-aggregators_and_integrators', 'subcategory-aggregators_and_integrators-aggregators_and_integrators-other': 'category-aggregators_and_integrators-aggregators_and_integrators', 'subcategory-aggregators_and_integrators-aggregators_and_integrators-services': 'category-aggregators_and_integrators-aggregators_and_integrators', 'subcategory-aggregators_and_integrators-aggregators_and_integrators-software': 'category-aggregators_and_integrators-aggregators_and_integrators', 'subcategory-other-other-other': 'category-other-other', 'subcategory-processing_and_analysis-data_analysis-2d_3d_digitisation': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-artificial_intelligence': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-data_exploitation': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-forecast': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-image_data_analysis': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-machine_learning': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-other': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-visualization': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_analysis-workflows': 'category-processing_and_analysis-data_analysis', 'subcategory-processing_and_analysis-data_management-access': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-annotation': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-anonymisation': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-brokering': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-digitisation': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-discovery': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-embargo': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-interlinking': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-maintenance': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-mining': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-other': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-persistent_identifier': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-preservation': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-publishing': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-registration': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-transfer': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-data_management-validation': 'category-processing_and_analysis-data_management', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-analysis': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-characterisation': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-maintenance_and_modification': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-other': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-production': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-testing_and_validation': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-validation': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-processing_and_analysis-measurement_and_materials_analysis-workflows': 'category-processing_and_analysis-measurement_and_materials_analysis', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-accounting': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-analysis': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-billing': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-configuration': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-coordination': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-helpdesk': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-monitoring': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-order_management': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-other': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-transportation': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-operations_and_infrastructure_management_services-utilities': 'category-security_and_operations-operations_and_infrastructure_management_services', 'subcategory-security_and_operations-security_and_identity-certification_authority': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-coordination': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-firewall': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-group_management': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-identity_and_access_management': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-other': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-single_sign_on': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-threat_protection': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-tools': 'category-security_and_operations-security_and_identity', 'subcategory-security_and_operations-security_and_identity-user_authentication': 'category-security_and_operations-security_and_identity', 'subcategory-sharing_and_discovery-applications-applications_repository': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-business': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-collaboration': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-communication': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-education': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-other': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-productivity': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-social_networking': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-applications-utilities': 'category-sharing_and_discovery-applications', 'subcategory-sharing_and_discovery-data-clinical_trial_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-data_archives': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-epidemiological_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-government_and_agency_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-online_service_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-other': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-scientific_research_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-data-statistical_data': 'category-sharing_and_discovery-data', 'subcategory-sharing_and_discovery-development_resources-apis_repository_gateway': 'category-sharing_and_discovery-development_resources', 'subcategory-sharing_and_discovery-development_resources-developer_tools': 'category-sharing_and_discovery-development_resources', 'subcategory-sharing_and_discovery-development_resources-other': 'category-sharing_and_discovery-development_resources', 'subcategory-sharing_and_discovery-development_resources-software_development_kits': 'category-sharing_and_discovery-development_resources', 'subcategory-sharing_and_discovery-development_resources-software_libraries': 'category-sharing_and_discovery-development_resources', 'subcategory-sharing_and_discovery-samples-biological_samples': 'category-sharing_and_discovery-samples', 'subcategory-sharing_and_discovery-samples-characterisation': 'category-sharing_and_discovery-samples', 'subcategory-sharing_and_discovery-samples-chemical_compounds_library': 'category-sharing_and_discovery-samples', 'subcategory-sharing_and_discovery-samples-other': 'category-sharing_and_discovery-samples', 'subcategory-sharing_and_discovery-samples-preparation': 'category-sharing_and_discovery-samples', 'subcategory-sharing_and_discovery-scholarly_communication-analysis': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-assessment': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-discovery': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-other': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-outreach': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-preparation': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-publication': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-scholarly_communication-writing': 'category-sharing_and_discovery-scholarly_communication', 'subcategory-sharing_and_discovery-software-libraries': 'category-sharing_and_discovery-software', 'subcategory-sharing_and_discovery-software-other': 'category-sharing_and_discovery-software', 'subcategory-sharing_and_discovery-software-platform': 'category-sharing_and_discovery-software', 'subcategory-sharing_and_discovery-software-software_package': 'category-sharing_and_discovery-software', 'subcategory-sharing_and_discovery-software-software_repository': 'category-sharing_and_discovery-software', 'subcategory-training_and_support-consultancy_and_support-application_optimisation': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-application_porting': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-application_scaling': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-audit_and_assessment': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-benchmarking': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-calibration': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-certification': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-consulting': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-methodology_development': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-modeling_and_simulation': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-other': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-prototype_development': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-software_development': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-software_improvement': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-technology_transfer': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-consultancy_and_support-testing': 'category-training_and_support-consultancy_and_support', 'subcategory-training_and_support-education_and_training-in_house_courses': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-online_courses': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-open_registration_courses': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-other': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-related_training': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-required_training': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-training_platform': 'category-training_and_support-education_and_training', 'subcategory-training_and_support-education_and_training-training_tool': 'category-training_and_support-education_and_training'}

    global ACCESS_MODES
    #if ACCESS_MODES is None:
    #    ACCESS_MODES = cv_retrieve.get_cv_values('ACCESS_MODE')
    #    print('****************ACCESS_MODES************')
    #    print(ACCESS_MODES)
    ACCESS_MODES = {'free': 'access_mode-free', 'free conditionally': 'access_mode-free_conditionally', 'other': 'access_mode-other', 'paid': 'access_mode-paid', 'peer reviewed': 'access_mode-peer_reviewed'}

    global ACCESS_TYPES
    #if ACCESS_TYPES is None:
    #    ACCESS_TYPES = cv_retrieve.get_cv_values('ACCESS_TYPE')
    #    print('****************ACCESS_TYPES************')
    #    print(ACCESS_TYPES)
    ACCESS_TYPES = {'mail-in': 'access_type-mail_in', 'other': 'access_type-other', 'physical': 'access_type-physical', 'remote': 'access_type-remote', 'virtual': 'access_type-virtual'}

    global LIFE_CYCLE_STATUS
    #if LIFE_CYCLE_STATUS is None:
    #    LIFE_CYCLE_STATUS = cv_retrieve.get_cv_values('LIFE_CYCLE_STATUS')
    #    print('****************LIFE_CYCLE_STATUS************')
    #    print(LIFE_CYCLE_STATUS)
    LIFE_CYCLE_STATUS = {'alpha': 'life_cycle_status-alpha', 'beta': 'life_cycle_status-beta', 'concept': 'life_cycle_status-concept', 'design': 'life_cycle_status-design', 'discovery': 'life_cycle_status-discovery', 'implementation': 'life_cycle_status-implementation', 'in containment': 'life_cycle_status-in_containment', 'operation': 'life_cycle_status-operation', 'other': 'life_cycle_status-other', 'planned': 'life_cycle_status-planned', 'preparation': 'life_cycle_status-preparation', 'production': 'life_cycle_status-production', 'retirement': 'life_cycle_status-retirement', 'termination': 'life_cycle_status-termination'}

    global PROVIDER_IDS
    #if PROVIDER_IDS is None:
    #    prov_names, prov_abbrevs = cv_retrieve.get_providers()
    #    PROVIDER_IDS = prov_names.values()
    #    print('****************PROVIDER_IDS************')
    #    print(PROVIDER_IDS)
    PROVIDER_IDS = ['surf-nl', 'esa-int', 'cyfronet', 'rbi', 'astron', 'f6snl', 'consorci_cee_lab_llum_sincrotro', 'ubora', 'grycap', 'norce', 'unibi-ub', 'smartsmear', 'meeo', 'msw', 'bineo', 'expertai', 'geant', 'compbiomed', 'taltechdata', 'infrafrontier', 'upf', 'isa-ulisboa', 'bsc-es', 'elixir-belgium', 'eudat', 'eosc-dih', 'carlzeissm', 'mobile_observation_integration_service', 'eiscat', 'inria', 'gcc_umcg', 'elixir-europe', 'ugr-es', 'ess_eric', 'riga_stradins_university', 'icos_eric', 'centerdata', 'sztaki', 'forth', 'elixir-uk', 'phenomenal', 'asgc', 'dcc-uk', 'rasdaman', 'hn', 'altec', 'siris_academic', 'elixir-italy', 'ill', 'cessda-eric', 'rli', 'cite', 'lnec', 'cineca', 'ror-org', 'upv-es', 'tubitak_ulakbim', 'clarin-eric', 'datacite', 'lnec-pt', 'osmooc', 'oslo_university', 'emso_eric', 'soleil', 'inode', 'cyberbotics', 'dynaikon', 'ukaea', 'ibiom-cnrhttpwwwibiomcnrit', 'bioexcel', 'niod', 'authenix', 'libnova', 'cnrsin2p3', 'jsc-de', 'umg-br', 'capsh', 'lindatclariah-cz', 'denbi', 'sobigdata', 'europeana', 'ehri', 'lago', 'enermaps', 'dariah_eric', 'cnr_-_isti', 'cnio', 'obp', 'egi-fed', 'unige', 'psi', 'aginfra', 'cnb-csic', 'vi-seem', 'gesis', 'inaf', 'csic', 'operas', 'grnet', 'gbif-es', 'ifca-csic', 'arkivum', 'iisas', 'ess', 'cerm-cirmmp', 'enhancer', 'cern', 'sstir', 'uni-freiburg', 'lsd-ufcg', 'eurac', 'coronis_computing_sl', 'sks', 'doabf', 'incd', 'cloudferro', 'figshare', 'crem', 'vamdc', 'creaf', 'lida', 'bi_insight', 'scigne', 'uit', 'cnr-iia', 'sixsq', 'plantnet', 'digitalglobe', 'up', 'readcoop', 'ds-wizard', 'unibo', 'openminted', 'jelastic', 'ceric-eric', 'scipedia', 'openknowledgemaps', 'prace', 'etais', 'seadatanet', 'openbiomaps', 'vecma', '100percentit', 'iict', 'acdh-ch', 'emphasis', 'bijvoetcenter', 'e-cam', 'csc-fi', 'kit', 'ubiwhere', 'cines', 'tib', 'hostkey', 'sites', 'gbif_portugal', 'cesnet', 'scai', 'd4science', 'inbelixir-es', 'olos', 'desy', 'komanord', 'wenmr', 'it4i_vsb-tuo', 'vilnius-university', 'ukri_-_stfc', 'mundi_web_services', 'terradue', 'esrf', 'instruct-eric', 'teledyne', 't-systems', 'eodc', 'trust-it', 'ipsl', 'sinergise', 'hzdr', 'athena', 'kit-scc', 'charles_university', 'infn', 'cy-biobank', 'cscs', 'treeofscience', 'iasa', 'cyi', 'cesga', 'predictia', 'edelweiss_connect', 'erasmusmc', 'idea', 'oxford_e-research_centre', 'obsparis', 'umr_map', 'fssda', 'openaire', 'ccsd', 'ifin-hh', 'switch', 'gsi', 'unifl', 'elsevier', 'naes_of_ukraine', 'creatis', 'earthwatch', 'unitartu', 'gbif', 'cs_group', 'bluebridge', 'collabwith', 'cc-in2p3cnrs', 'unimib', 'genias', 'openedition', 'sciences_po', 'cmcc', 'cds', 'psnc', 'lifewatch-eric', 'csi_piemonte', 'european_xfel', 'mi', 'dkrz', 'blue-cloud', 'ciemat-tic', 'data_revenue', 'mz', 'coard', 'uni_konstanz', 'diamond_light_source', 'gwdg', 'eox', 'forschungsdaten', 'ifremer', 'crg', 'materialscloud', 'fairdi', 'exoscale', 'euro-argo', 'suite5', 'demo', 'embl-ebi']

    global COUNTRIES
    #if COUNTRIES is None:
    #    COUNTRIES = cv_retrieve.get_cv_values('COUNTRY')
    #    with open('countries.txt', 'w') as myf:
    #        myf.write(';'.join(COUNTRIES))
    #    print('****************COUNTRIES************')
    #    print(COUNTRIES)
    COUNTRIES = {'andorra': 'AD', 'united arab emirates (the)': 'AE', 'afghanistan': 'AF', 'antigua and barbuda': 'AG', 'anguilla': 'AI', 'albania': 'AL', 'armenia': 'AM', 'angola': 'AO', 'antarctica': 'AQ', 'argentina': 'AR', 'american samoa': 'AS', 'austria': 'AT', 'australia': 'AU', 'aruba': 'AW', 'åland islands': 'AX', 'azerbaijan': 'AZ', 'bosnia and herzegovina': 'BA', 'barbados': 'BB', 'bangladesh': 'BD', 'belgium': 'BE', 'burkina faso': 'BF', 'bulgaria': 'BG', 'bahrain': 'BH', 'burundi': 'BI', 'benin': 'BJ', 'saint barthélemy': 'BL', 'bermuda': 'BM', 'brunei darussalam': 'BN', 'bolivia, plurinational state of': 'BO', 'bonaire, sint eustatius and saba': 'BQ', 'brazil': 'BR', 'bahamas (the)': 'BS', 'bhutan': 'BT', 'bouvet island': 'BV', 'botswana': 'BW', 'belarus': 'BY', 'belize': 'BZ', 'canada': 'CA', 'cocos (keeling) islands (the)': 'CC', 'congo (the democratic republic of the)': 'CD', 'central african republic (the)': 'CF', 'congo (the)': 'CG', 'switzerland': 'CH', "côte d'ivoire": 'CI', 'cook islands (the)': 'CK', 'chile': 'CL', 'cameroon': 'CM', 'china': 'CN', 'colombia': 'CO', 'costa rica': 'CR', 'cuba': 'CU', 'cabo verde': 'CV', 'curaçao': 'CW', 'christmas island': 'CX', 'cyprus': 'CY', 'czechia': 'CZ', 'germany': 'DE', 'djibouti': 'DJ', 'denmark': 'DK', 'dominica': 'DM', 'dominican republic (the)': 'DO', 'algeria': 'DZ', 'ecuador': 'EC', 'estonia': 'EE', 'egypt': 'EG', 'western sahara': 'EH', 'greece': 'EL', 'eritrea': 'ER', 'spain': 'ES', 'ethiopia': 'ET', 'finland': 'FI', 'fiji': 'FJ', 'falkland islands (the) [malvinas]': 'FK', 'micronesia (federated states of)': 'FM', 'faroe islands': 'FO', 'france': 'FR', 'gabon': 'GA', 'grenada': 'GD', 'georgia': 'GE', 'french guiana': 'GF', 'guernsey': 'GG', 'ghana': 'GH', 'gibraltar': 'GI', 'greenland': 'GL', 'gambia (the)': 'GM', 'guinea': 'GN', 'guadeloupe': 'GP', 'equatorial guinea': 'GQ', 'south georgia and the south sandwich islands': 'GS', 'guatemala': 'GT', 'guam': 'GU', 'guinea-bissau': 'GW', 'guyana': 'GY', 'hong kong': 'HK', 'heard island and mcdonald islands': 'HM', 'honduras': 'HN', 'croatia': 'HR', 'haiti': 'HT', 'hungary': 'HU', 'indonesia': 'ID', 'ireland': 'IE', 'israel': 'IL', 'isle of man': 'IM', 'india': 'IN', 'british indian ocean territory (the)': 'IO', 'iraq': 'IQ', 'iran (islamic republic of)': 'IR', 'iceland': 'IS', 'italy': 'IT', 'jersey': 'JE', 'jamaica': 'JM', 'jordan': 'JO', 'japan': 'JP', 'kenya': 'KE', 'kyrgyzstan': 'KG', 'cambodia': 'KH', 'kiribati': 'KI', 'comoros (the)': 'KM', 'saint kitts and nevis': 'KN', "korea (the democratic people's republic of)": 'KP', 'korea (the republic of)': 'KR', 'kuwait': 'KW', 'cayman islands (the)': 'KY', 'kazakhstan': 'KZ', "lao people's democratic republic (the)": 'LA', 'lebanon': 'LB', 'saint lucia': 'LC', 'liechtenstein': 'LI', 'sri lanka': 'LK', 'liberia': 'LR', 'lesotho': 'LS', 'lithuania': 'LT', 'luxembourg': 'LU', 'latvia': 'LV', 'libya': 'LY', 'morocco': 'MA', 'monaco': 'MC', 'moldova (republic of)': 'MD', 'montenegro': 'ME', 'saint martin (french part)': 'MF', 'madagascar': 'MG', 'marshall islands (the)': 'MH', 'north macedonia': 'MK', 'mali': 'ML', 'myanmar': 'MM', 'mongolia': 'MN', 'macao': 'MO', 'northern mariana islands (the)': 'MP', 'martinique': 'MQ', 'mauritania': 'MR', 'montserrat': 'MS', 'malta': 'MT', 'mauritius': 'MU', 'maldives': 'MV', 'malawi': 'MW', 'mexico': 'MX', 'malaysia': 'MY', 'mozambique': 'MZ', 'namibia': 'NA', 'new caledonia': 'NC', 'niger (the)': 'NE', 'norfolk island': 'NF', 'nigeria': 'NG', 'nicaragua': 'NI', 'netherlands (the)': 'NL', 'norway': 'NO', 'nepal': 'NP', 'nauru': 'NR', 'niue': 'NU', 'new zealand': 'NZ', 'oman': 'OM', 'other': 'OT', 'panama': 'PA', 'peru': 'PE', 'french polynesia': 'PF', 'papua new guinea': 'PG', 'philippines (the)': 'PH', 'pakistan': 'PK', 'poland': 'PL', 'saint pierre and miquelon': 'PM', 'pitcairn': 'PN', 'puerto rico': 'PR', 'palestine, state of': 'PS', 'portugal': 'PT', 'palau': 'PW', 'paraguay': 'PY', 'qatar': 'QA', 'réunion': 'RE', 'romania': 'RO', 'serbia': 'RS', 'russian federation (the)': 'RU', 'rwanda': 'RW', 'saudi arabia': 'SA', 'solomon islands': 'SB', 'seychelles': 'SC', 'sudan (the)': 'SD', 'sweden': 'SE', 'singapore': 'SG', 'saint helena, ascension and tristan da cunha': 'SH', 'slovenia': 'SI', 'svalbard and jan mayen': 'SJ', 'slovakia': 'SK', 'sierra leone': 'SL', 'san marino': 'SM', 'senegal': 'SN', 'somalia': 'SO', 'suriname': 'SR', 'south sudan': 'SS', 'são tomé and príncipe': 'ST', 'el salvador': 'SV', 'sint maarten (dutch part)': 'SX', 'syrian arab republic (the)': 'SY', 'eswatini': 'SZ', 'turks and caicos islands (the)': 'TC', 'chad': 'TD', 'french southern territories (the)': 'TF', 'togo': 'TG', 'thailand': 'TH', 'tajikistan': 'TJ', 'tokelau': 'TK', 'timor-leste': 'TL', 'turkmenistan': 'TM', 'tunisia': 'TN', 'tonga': 'TO', 'turkey': 'TR', 'trinidad and tobago': 'TT', 'tuvalu': 'TV', 'taiwan (province of china)': 'TW', 'tanzania, united republic of': 'TZ', 'ukraine': 'UA', 'uganda': 'UG', 'united kingdom of great britain and northern ireland (the)': 'UK', 'united states minor outlying islands': 'UM', 'united states of america (the)': 'US', 'uruguay': 'UY', 'uzbekistan': 'UZ', 'holy see (the)': 'VA', 'saint vincent and the grenadines': 'VC', 'venezuela (bolivarian republic of)': 'VE', 'virgin islands (british)': 'VG', 'virgin islands (u.s.)': 'VI', 'viet nam': 'VN', 'vanuatu': 'VU', 'wallis and futuna': 'WF', 'samoa': 'WS', 'yemen': 'YE', 'mayotte': 'YT', 'south africa': 'ZA', 'zambia': 'ZM', 'zimbabwe': 'ZW', 'middle earth': 'country-middle_earth'}

    global TARGET_USERS
    #if TARGET_USERS is None:
    #    TARGET_USERS = cv_retrieve.get_cv_values('TARGET_USER')
    TARGET_USERS = {'businesses': 'target_user-businesses', 'funders': 'target_user-funders', 'innovators': 'target_user-innovators', 'other': 'target_user-other', 'policy makers': 'target_user-policy_makers', 'providers': 'target_user-providers', 'research communities': 'target_user-research_communities', 'research groups': 'target_user-research_groups', 'research infrastructure managers': 'target_user-research_infrastructure_managers', 'research managers': 'target_user-research_managers', 'research networks': 'target_user-research_networks', 'research organisations': 'target_user-research_organisations', 'research projects': 'target_user-research_projects', 'researchers': 'target_user-researchers', 'resource managers': 'target_user-resource_managers', 'resource provider managers': 'target_user-resource_provider_managers', 'students': 'target_user-students'}



    #################################
    ### Start collecting metadata ###
    #################################

    ##################################
    ### Items extractable directly ###
    ### (without iterating)        ###
    ##################################
    # First, we collect the values where no iterating over the
    # Blue-Cloud catalogue is necessary, as we can extract them
    # directly.
    
    # WIP: I think we don't have this at this point! WIP TODO HEUTE
    blue_id = md['id']
    # This is the Blue-Cloud id, which is not the EOSC id!
    # But for validating, we need some id.
    #check_is_string(id_, 'id', True, 30, collected_messages)

    # EOSC wants a "name", which is filled by Blue-Cloud's "title", 
    # while Blue-Cloud also has a "name".
    eosc_name = md['title']
    bc_name = md['name']
    abbreviation = ABBREVIATIONS[bc_name]
    check_is_string(abbreviation, 'abbreviation', True, 20, collected_messages)
    check_is_string(eosc_name, 'eosc_name', True, 80, collected_messages)
    log_value(LOGGER, abbreviation, 'abbreviation')
    log_value(LOGGER, eosc_name, 'eosc_name')

    version = md['version']
    check_is_string(version, 'version', False, 10, collected_messages)
    log_value(LOGGER, version, 'version')

    # Using "notes" for description, and shortening it as discussed with Leonardo Candela:
    # See: https://support.d4science.org/issues/23145
    description = md['notes']
    len_desc = len(description)
    LOGGER.debug('description: Length %s chars.' % len_desc)
    if len_desc > 1000:
        add = ' ... (For more details, please visit the service webpage!)'
        new_desc = description[0:1000-len(add)] + add
        LOGGER.debug('description: Shortened description to %s' % len(new_desc))
        description = new_desc
    log_value(LOGGER, description[0:35]+'...', 'description')


    ### These are taken from the list "tags"
    ### (containing composite items in Blue-Cloud, flattened for EOSC):
    tags = []
    for item in md['tags']:
        tags.append(item['display_name'])
        check_is_string(item['display_name'], 'tags', False, 50, collected_messages)
        # These will be filtered and printed further down..


    #####################################
    ### Define variables to be filled ###
    ### from list "extras"            ###
    #####################################

    ### Basic Information:
    # id = (above)
    # abbreviation = (above)
    # eosc_name = (above)
    resourceOrganisation = ''
    resourceProviders = []
    webpage = ''

    ### Marketing Information:
    # description = (above)
    tagline = ''
    logo = ''
    multimedia_composite, multimedia_url, multimedia_name = [], '', '' # Will be composed to dict later
    use_cases_composite, use_case_url, use_case_name = [], '', '' # Will be composed to dict later

    ### Classification Information:
    domain_ids, subdomain_ids = [], [] # Will be composed to dicts later
    domain_names = [] # Names for filtering tags later
    category_ids, subcategory_ids = [], [] # Will be composed to dicts later
    category_names = [] # Names for filtering tags later
    targetUsers, targetUsersNames = [], [] # Names for filtering tags later
    accessTypes = []
    accessModes = []
    # tags = (above)

    ### Geographical and Language Availability Information
    geographicalAvailabilities = []
    languageAvailabilities = []

    ### Resource Location Information
    resourceGeographicLocations = []

    ### Contact Information
    maincontact_firstName, maincontact_lastName = '', ''
    maincontact_email, maincontact_phone = '', ''
    maincontact_position = ''
    maincontact_organisation = ''
    publiccontact_firstName, publiccontact_lastName = '', ''
    publiccontact_email, publiccontact_phone = '', ''
    publiccontact_position = ''
    publiccontact_organisation = ''
    helpdeskEmail = ''
    securityContactEmail = ''

    ### Maturity Information
    trl = ''
    lifeCycleStatus = ''
    certifications = []
    standards = []
    openSourceTechnologies = []
    # version = (above)
    lastUpdate = ''
    changeLogs = []

    ### Dependencies Information
    requiredResources = []
    relatedResources = []
    relatedPlatforms = []
    catalogue = ''

    ### Attribution Information
    fundingBodies = []
    fundingPrograms = []
    grantProjectNames = []

    ### Management Information
    helpdeskPage = ''
    userManual = ''
    termsOfUse = ''
    privacyPolicy = ''
    accessPolicy = ''
    serviceLevel = '' # profile version 3
    resourceLevel = '' # profile version 4
    trainingInformation = ''
    statusMonitoring = ''
    maintenance = ''

    ### Access and Order information
    order = ''
    orderType = ''

    ### Financial Information
    paymentModel = ''
    pricing = ''


    ##########################
    ### Start iterating    ###
    ### over list "extras" ###
    ##########################

    for item in md['extras']:

        ### Basic Information:

        # id is dealt with above
        # abbrevation is dealt with above
        # name (eosc_name) is dealt with above

        if item['key'] == 'BasicInformation:Resource Organisation':
            # mandatory, 1 provider id
            # Apparently, this **must be** "blue-cloud". In the GUI, we have no
            # other option, as we have admin permissions only for "blue-cloud".
            #
            # Currently filled values (2022-04-15) are:
            # Providers that exist as EOSC provider:
            # * Blue-Cloud (exists, just lower case needed)
            # * IFREMER (exists, just lower case needed)
            # * CMCC Foundation (exsists, just abbreviation needed)
            # Providers that do not exist as EOSC provier:
            # * Bjerknes Climate Data Centre, Geophysical Institute, University of Bergen (does not exist)
            # * KNMI (does not exist)
            # Wiki: https://redmine.dkrz.de/projects/bluecloud/wiki/Protocol_tech#Some-notes
            resourceOrganisation = item['value'].strip()

            if resourceOrganisation == 'blue-cloud':
                LOGGER.debug('resourceOrganisation: Is already "blue-cloud", great!')
           
            elif resourceOrganisation == 'Blue-Cloud':
                # This is the case in various services:
                # modelling_phyto_zoo_plankton_interactions, phytoplankton_eovs, zoo_and_phytoplankton_essential_ocean_variable_products_vlab
                msg = 'resourceOrganisation: Corrected field content: "%s" -> "blue-cloud"!' % resourceOrganisation
                LOGGER.debug(msg)
                resourceOrganisation = 'blue-cloud'

            elif len(resourceOrganisation) == 0:
                msg = 'resourceOrganisation is an empty string.'
                collected_messages.append(msg)
           
            else:
                msg = 'REPORTED TODO: resourceOrganisation: Replaced content "%s" with "blue-cloud"! https://support.d4science.org/issues/23182' % resourceOrganisation
                collected_messages.append(msg)
                resourceOrganisation = 'blue-cloud'
                # TODO Wait for issue: https://support.d4science.org/issues/23182
                # TODO Consider issue: https://support.d4science.org/issues/23119
                msg = 'REPORTED TODO: Should I move the original value to resourceProviders? -> https://support.d4science.org/issues/23182'
                collected_messages.append(msg)

            log_value(LOGGER, resourceOrganisation, 'resourceOrganisation')


        elif item['key'] == 'BasicInformation:Resource Provider':
            # optional, multiple provider ids
            # Currently ocurring values are (2022-04-15):
            # * empty (4x) --> https://support.d4science.org/issues/23120
            # * https://data.d4science.org/ctlg/Blue-CloudProject/blue-cloud_virtual_research_environment (3x) (URL is not valid, replace by d4science?) --> https://support.d4science.org/issues/23183
            # * KNMI (1x)(does not exist as eosc provider: Throw away or replace?) --> https://support.d4science.org/issues/23120
            # Wiki: https://redmine.dkrz.de/projects/bluecloud/wiki/Protocol_tech#Some-notes

            tmp = item['value'].strip()
            if len(tmp) == 0:
                msg = 'REPORTED TODO: Provider empty. Add d4science? https://support.d4science.org/issues/23120'
                collected_messages.append(msg)
                # Add "d4science"? --> https://support.d4science.org/issues/23120
            else:
                LOGGER.debug('resourceProvider originally set to: %s' % tmp)

            if tmp == 'D4Science': # TODO TEST DOES THIS SOLVE? DO WE HAVE TO REPORT? WIP HEUTE
                # This is the case in this services:
                # marine_environmental_indicators_vlab
                LOGGER.debug('resourceProvider: Corrected field content: "%s" -> "d4science"!' % tmp)
                tmp = 'd4science'

            elif tmp == 'KNMI':
                pass
                # Only in "storm_severity_index_ssi_notebook" (2022-04-15)
                # TODO This has to be fixed by them! Or just leave out? --> https://support.d4science.org/issues/23120
                new = 'd4science'
                msg = 'REPORTED TODO: Corrected field "resourceProviders": "%s" with "%s"!' % (tmp, new)
                collected_messages.append(msg)
                tmp = new

            if tmp == 'https://data.d4science.org/ctlg/Blue-CloudProject/blue-cloud_virtual_research_environment':
                # E.g. in phytoplanktion_eovs, zoo_and_phytoplankton_essential_ocean_variable_products_vlab., modelling_phyto_zoo_plankton_interactions
                # TODO: Wait for issue https://support.d4science.org/issues/23183 to see if I should fix this!
                new = 'd4science'
                msg = 'REPORTED TODO: Corrected field "resourceProviders": "%s" with "%s"! --> https://support.d4science.org/issues/23183' % (tmp, new)
                collected_messages.append(msg)
                tmp = new

            if PROVIDER_IDS is None:
                LOGGER.warning('Cannot check provider id right now due to server error.')
            else:
                # WIP TEST THESE TWO:
                check_is_in_cv(tmp, 'BasicInformation:Resource Provider', True, PROVIDER_IDS, 'Provider Ids')
                if len(tmp) > 0 and not tmp in PROVIDER_IDS:
                    msg = 'Provider id "%s" not in list of ids! May fail validation.' % tmp
                    collected_messages.append(msg)

            log_value(LOGGER, tmp, 'resourceProvider')
            resourceProviders.append(tmp)


        elif item['key'] == 'BasicInformation:Webpage':
            # mandatory, 1 url
            webpage = item['value'].strip()
            check_is_url(webpage, 'webpage', True, collected_messages)
            log_value(LOGGER, webpage, 'webpage')
            # I considered using the "Item URL" as alternative, in case this is missing, but Leonardo prefered to use Webpage.
            # See discussions: https://support.d4science.org/issues/23124
            # The item URL is a pointer to the catalog entry, it is automatically generated.
            # The webpage is something every creator of a service entry into the catalogue is free to compile as he/she likes. 
            # This is expected to be a link to the webpage of the specific service. I would suggest to not get rid of the webpage
            # in favor of the item URL simply because the compiler of the catalog entry is compiling it when describing the specific service.

        ### Basic Information: Done ###

        ### Marketing Information: ###

        # description is dealt with above!

        elif item['key'] == 'MarketingInformation:Tagline':
            # mandatory, 1 string
            tagline = item['value'].strip()
            check_is_string(tagline, 'tagline', True, 100, collected_messages)
            log_value(LOGGER, tagline, 'tagline')

        elif item['key'] == 'MarketingInformation:Logo':
            # mandatory, 1 url
            logo = item['value'].strip()
            check_is_url(logo, 'logo', True, collected_messages)
            log_value(LOGGER, logo, 'logo')
            # I considered using "organization" -> "image_url" if logo is missing, but
            # Leonardo would rather fix the missing logo:
            # See discussion in : https://support.d4science.org/issues/23143

        elif item['key'] == 'MarketingInformation:Multimedia':
            # optional, multiple urls (we allow just one)
            multimedia_url = item['value'].strip()
            check_is_url(multimedia_url, 'multimedia_url', False, collected_messages)
            log_value(LOGGER, multimedia_url, 'multimedia_url')
            # EOSC allows several, but we allow only one.

        elif item['key'] == 'MarketingInformation:Multimedia Name':
            # optional, multiple strings (we allow just one)
            multimedia_name = item['value'].strip()
            check_is_string(multimedia_name, 'multimedia_name', False, 100, collected_messages)
            log_value(LOGGER, multimedia_name, 'multimedia_name')
            # EOSC allows several, but we allow only one.

        elif item['key'] == 'MarketingInformation:Use Case':
            # optional, multiple urls (we allow just one)
            use_case_url = item['value'].strip()
            check_is_url(use_case_url, 'use_case_url', False, collected_messages)
            log_value(LOGGER, use_case_url, 'use_case_url')
            # EOSC allows several, but we allow only one.

        elif item['key'] == 'MarketingInformation:Use Case Name':
            # optional, multiple strings (we allow just one)
            use_case_name = item['value'].strip()
            check_is_string(use_case_name, 'use_case_name', False, 100, collected_messages)
            log_value(LOGGER, use_case_name, 'use_case_name')
            # EOSC allows several, but we allow only one.

        ### Marketing Information: Done ###

        ### Classification Information: ###

        # Note: Composite objects are constructed after the iteration,
        # here we just collect the values.

        elif item['key'] == 'ClassificationInformation:Scientific Domain':
            # mandatory, multiple cv values
            # We need the domain id!
            # Values are given like this: 'Natural Sciences'
            dom_name = item['value'].strip()
            domain_names.append(dom_name)  # For filtering tags later!
            dom_id = CV_DOM[dom_name.lower()]
            domain_ids.append(dom_id)
            log_value(LOGGER, '%s" ("%s")' % (dom_id, dom_name), 'scientificDomain')

        elif item['key'] == 'ClassificationInformation:Scientific Subdomain':
            # mandatory, multiple cv values
            # We need the subdomain id!
            # Values are given like this: 'Natural Sciences.Other natural sciences'
            subdom_name_long = item['value'].strip()

            # TODO REMOVE THIS HACK:
            if ' and ' in subdom_name_long:
                msg = 'REPORTED TODO: and/& in subdom_name_long: %s' % subdom_name_long
                collected_messages.append(msg)
                subdom_name_long = subdom_name_long.replace(' and ', ' & ')

            subdom_name = subdom_name_long.split('.')[1]
            subdom_id = CV_SUBDOM[subdom_name_long.lower()]
            subdomain_ids.append(subdom_id)
            log_value(LOGGER, '%s" ("%s")' % (subdom_id, subdom_name_long), 'scientificSubdomain')

        elif item['key'] == 'ClassificationInformation:Category':
            # mandatory, multiple cv values
            # We need the category id!
            # Values are given like this: ...
            cat_name = item['value'].strip()
            category_names.append(cat_name) # For filtering tags later!

            if cat_name == 'Application':
                msg = 'PROBLEM AT EOSC: Application without s in cat_name: https://support.d4science.org/issues/23180'
                collected_messages.append(msg)
                cat_name = 'Applications'

            # TODO REMOVE THESE HACK: MAKE ISSUE
            if ' and ' in cat_name:
                msg ='REPORTED TODO: and/& in cat_name: %s: https://support.d4science.org/issues/23173' % cat_name
                collected_messages.append(msg)
                cat_name = cat_name.replace(' and ', ' & ')

            cat_id = CV_CAT[cat_name.lower()]
            category_ids.append(cat_id)
            log_value(LOGGER, '%s" ("%s")' % (cat_id, cat_name), 'category')

        elif item['key'] == 'ClassificationInformation:Subcategory':
            # mandatory, multiple cv values
            # We need the subcategory id!
            # Values are given like this: ...
            subcat_name_long = item['value'].strip()

            # TODO REMOVE THIS HACK: MAKE ISSUE
            if 'Application.' in subcat_name_long:
                msg = 'REPORTED HACK: Application without s in subcat_name_long: https://support.d4science.org/issues/23180'
                collected_messages.append(msg)
                subcat_name_long = subcat_name_long.replace('Application.', 'Applications.')
            if 'Development Resource.' in subcat_name_long:
                msg = 'REPORTED HACK: Development Resource. without s in subcat_name_long: https://support.d4science.org/issues/23180'
                collected_messages.append(msg)
                subcat_name_long = subcat_name_long.replace('Development Resource.', 'Development Resources.')
            if ' and ' in subcat_name_long:
                msg = 'REPORTED HACK: and/& in subcategory: %s: https://support.d4science.org/issues/23173' % subcat_name_long
                collected_messages.append(msg)
                subcat_name_long = subcat_name_long.replace(' and ', ' & ')
            
            subcat_name = subcat_name_long.split('.')[1]
            subcat_id = CV_SUBCAT[subcat_name_long.lower()]
            subcategory_ids.append(subcat_id)
            log_value(LOGGER, '%s" ("%s")' % (subcat_id, subcat_name_long), 'subcategory')

        elif item['key'] == 'ClassificationInformation:Target User':
            # mandatory, multiple cv values
            value_bluecloud = item['value'].strip()

            # TODO REMOVE DIRTY HACK:
            if value_bluecloud == 'Researcher groups':
                corrected = 'Research Groups'
                msg = 'REPORTED HACK: replaced field "targetUsers": "%s" with "%s"! https://support.d4science.org/issues/23184' % (value_bluecloud, corrected)
                collected_messages.append(msg)
                value_bluecloud = corrected

            value_eosc = TARGET_USERS[value_bluecloud.lower()]
            targetUsersNames.append(value_bluecloud) # For filtering tags later
            targetUsers.append(value_eosc)
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'targetUsers')

        elif item['key'] == 'ClassificationInformation:Access Type':
            # optional, multiple cv values
            value_bluecloud = item['value'].strip()
            value_eosc = ACCESS_TYPES[value_bluecloud.lower()]
            accessTypes.append(value_eosc)
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'accessTypes')

        elif item['key'] == 'ClassificationInformation:Access Mode':
            # optional, multiple cv values
            value_bluecloud = item['value'].strip()
            value_eosc = ACCESS_MODES[value_bluecloud.lower()]
            accessModes.append(value_eosc)
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'accessModes')

        # tags are dealt with above!

        ### Classification Information: Done ###

        ### Geographical and Language Availability Information ###

        elif item['key'] == 'AvailabilityInformation:Geographical Availability':
            # mandatory, multiple cv values
            # Get proper value from passed value itself:
            # We get:  "Europe (EO)", Worldwide (WW)
            # We need: "EO", "WW"
            tmp = item['value'].strip()
            value_bluecloud, value_eosc = tmp.split(' (')
            value_eosc = value_eosc.rstrip(')')
            # TODO Check if this value conforms to CV.
            if len(value_eosc) > 0:
                geographicalAvailabilities.append(value_eosc)
                log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'geographicalAvailabilities')
            else:
                msg = 'Empty string passed for mandatory Geographical Availability'
                collected_messages.append(msg)

        elif item['key'] == 'AvailabilityInformation:Language Availability':
            # mandatory, multiple cv values
            # Get proper value from the passed values itself:
            # We get: "English (en)"
            # We need: "en"
            tmp = item['value'].strip()
            value_bluecloud, value_eosc = tmp.split(' (')
            value_eosc = value_eosc.rstrip(')')
            # TODO Check if this value conforms to CV.
            if len(value_eosc) > 0:
                languageAvailabilities.append(value_eosc)
                log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'languageAvailabilities')
            else:
                msg = 'Empty string passed for mandatory Language Availability'
                collected_messages.append(msg)

        ### Geographical and Language Availability Information: Done ###
        
        ### Resource Location Information ###

        elif item['key'] == 'LocationInformation:Resource Geographic Location':
            # optional, multiple cv values
            # https://eosc-portal.eu/providers-documentation/eosc-provider-portal-resource-profile#Resource%20Geographic%20Location

            # Split value:        
            orig = item['value'].strip()
            tmp = orig.split(' (')
            # TODO: One of the following should not exist, see
            # https://support.d4science.org/issues/23199
            if len(tmp) == 2:
                # We get:  "Italy (IT)"
                # We need: "IT"
                name = tmp[0]
                abbrev = tmp[1]
                abbrev = abbrev.rstrip(')')
            else:
                msg = 'REPORTED EOSC PROBLEM: Inconsistent field resourceGeographicLocations. See https://support.d4science.org/issues/23199'
                collected_messages(msg)
                # We get:  "Other"
                # We need: "OT"
                name = tmp[0]

            # Get proper value from CV:
            try:
                eosc_id = COUNTRIES[name.lower()]
                resourceGeographicLocations.append(eosc_id)
            except KeyError:
                msg = 'Could not map "resourceGeographicLocations": "%s" not in list of countries: %s' % (name.lower(), COUNTRIES.keys())
                collected_messages.append(msg)
                resourceGeographicLocations.append(name)
            
            tmplog = 'id "%s" (original "%s", name "%s")' % (eosc_id, orig, name)
            log_value(LOGGER, tmplog, 'resourceGeographicLocations')

        ### Resource Location Information: Done ###

        ### Contact Information: Main ###

        # Note: A composite object is constructed after the iteration,
        # here we just collect the values.

        elif item['key'] == 'ContactInformation:Main Contact Name':
            # mandatory, 1 string
            # Hoping there will be just one first and one last name, see https://support.d4science.org/issues/23148
            maincontact_name = item['value'].strip()
            log_value(LOGGER, maincontact_name, 'maincontact_name (to be splitted)')

        elif item['key'] == 'ContactInformation:Main Contact Email':
            # mandatory, 1 email
            maincontact_email = item['value'].strip()
            check_is_email(maincontact_email, 'maincontact_email', True, collected_messages)
            log_value(LOGGER, maincontact_email, 'maincontact_email')

        elif item['key'] == 'ContactInformation:Main Contact Phone':
            # optional, 1 string
            maincontact_phone = item['value'].strip()
            check_is_string(maincontact_phone, 'maincontact_phone', False, 20, collected_messages)
            log_value(LOGGER, maincontact_phone, 'maincontact_phone')

        elif item['key'] == 'ContactInformation:Main Contact Position':
            # optional, 1 string
            maincontact_position = item['value'].strip()
            check_is_string(maincontact_position, 'maincontact_position', False, 20, collected_messages)
            log_value(LOGGER, maincontact_position, 'maincontact_position')

        elif item['key'] == 'ContactInformation:Main Contact Organisation':
            # optional, 1 string
            maincontact_organisation = item['value'].strip()

            # TODO Apparently I have to manually correct here! WIP TODO HEUTE COMPLAIN BLA
            if maincontact_organisation == 'Centro Euro-Mediterraneo sui Cambiamenti Climatici CMCC':
                LOGGER.warning('maincontact_organisation originally set to: %s. Changing to "cmcc".' % maincontact_organisation)
                maincontact_organisation = 'cmcc'

            check_is_string(maincontact_organisation, 'maincontact_organisation', False, 50, collected_messages)
            log_value(LOGGER, maincontact_organisation, 'maincontact_organisation')

        ### Contact Information: Main: Done ###

        ### Contact Information: Public ###

        # Note: A composite object is constructed after the iteration,
        # here we just collect the values.

        elif item['key'] == 'ContactInformation:Public Contact Name':
            # optional, 1 string
            # Hoping there will be just one first and one last name:
            publiccontact_name = item['value'].strip()
            log_value(LOGGER, publiccontact_name, 'publiccontact_name (to be splitted)')

            '''
            Note: EOSC allows several (composite) public contacts, but in the
            BlueCloud model this is not possible, so we won't enable several
            public contacts in this mapping!
            Why? Blue-Cloud lists all their properties independently, so we cannot
            re-compose a composite type from those independent properties.
            '''

        elif item['key'] == 'ContactInformation:Public Contact Email':
            # mandatory, 1 email
            publiccontact_email = item['value'].strip()
            check_is_email(publiccontact_email, 'publiccontact_email', True, collected_messages)
            log_value(LOGGER, publiccontact_email, 'publiccontact_email')

        elif item['key'] == 'ContactInformation:Public Contact Phone':
            # optional, 1 string
            publiccontact_phone = item['value'].strip()
            check_is_string(publiccontact_phone, 'publiccontact_phone', False, 20, collected_messages)
            log_value(LOGGER, publiccontact_phone, 'publiccontact_phone')

        elif item['key'] == 'ContactInformation:Public Contact Position':
            # optional, 1 string
            publiccontact_position = item['value'].strip()
            check_is_string(publiccontact_position, 'publiccontact_position', False, 20, collected_messages)
            log_value(LOGGER, publiccontact_position, 'publiccontact_position')

        elif item['key'] == 'ContactInformation:Public Contact Organisation':
            # optional, 1 string
            publiccontact_organisation = item['value'].strip()
            check_is_string(publiccontact_organisation, 'publiccontact_organisation', False, 50, collected_messages)
            log_value(LOGGER, publiccontact_organisation, 'publiccontact_organisation')

        ### Contact Information: Public: Done ###

        ### Contact Information: Other: ###

        elif item['key'] == 'ContactInformation:Helpdesk Email':
            # mandatory, 1 email
            helpdeskEmail = item['value'].strip()
            check_is_email(helpdeskEmail, 'helpdeskEmail', True, collected_messages)
            log_value(LOGGER, helpdeskEmail, 'helpdeskEmail')

        elif item['key'] == 'ContactInformation:Security Contact Email':
            # mandatory, 1 email
            securityContactEmail = item['value'].strip()
            check_is_email(securityContactEmail, 'securityContactEmail', True, collected_messages)
            log_value(LOGGER, securityContactEmail, 'securityContactEmail')

        ### Contact Information: Other: Done ###

        ### Maturity Information: ###

        elif item['key'] == 'MaturityInformation:Technology Readiness Level':
            # mandatory, 1 cv value
            # Get proper value from the passed values itself:
            # They contain combined values of the TLR and the description.
            # We get:  "TRL4 Technology validated in lab"
            # We need: "trl-4"
            value_eosc = None
            value_bluecloud = item['value'].strip()
            if len(value_bluecloud)>0 and value_bluecloud.startswith('TRL'):
                tmp = value_bluecloud.split(' ')[0]
                trl_int = int(tmp.replace('TRL', ''))
                value_eosc = tmp.replace('TRL', 'trl-')
            trl = value_eosc
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'trl')
            # WIP HEUTE TODO CHECK IS CV

        elif item['key'] == 'MaturityInformation:Life Cycle Status':
            # optional, 1 cv value
            value_bluecloud = item['value'].strip()
            value_eosc = LIFE_CYCLE_STATUS[value_bluecloud.lower()]
            lifeCycleStatus = value_eosc
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'lifeCycleStatus')

        elif item['key'] == 'MaturityInformation:Certifications':
            # optional, multiple strings
            certi = item['value'].strip()
            check_is_string(certi, "certifications", False, 100, collected_messages)
            if len(certi) > 0:
                certifications.append(certi)
                log_value(LOGGER, certi, 'certification')
            #else:
            #    msg = 'Empty string passed for optional Certifications'
            #    collected_messages.append(msg)

        elif item['key'] == 'MaturityInformation:Standards': # TODO ASK Or is this to be splitted?
            # optional, multiple strings
            standard = item['value'].strip()
            check_is_string(standard, "standards", False, 100, collected_messages)
            if len(standard) > 0:
                standards.append(standard)
                log_value(LOGGER, standard, 'standard')
            #else:
            #    msg = 'Empty string passed for optional Standards'
            #    collected_messages.append(msg)

        elif item['key'] == 'MaturityInformation:Open Source Technologies': # TODO ASK Or is this to be splitted?
            # optional, multiple strings
            openSourceTech = item['value']
            check_is_string(openSourceTech, "openSourceTechnologies", False, 100, collected_messages)
            if len(openSourceTech) > 0:
                openSourceTechnologies.append(openSourceTech)
                log_value(LOGGER, openSourceTech, 'openSourceTechnology')
            #else:
            #    msg = 'Empty string passed for optional Open Source Technologies'
            #    collected_messages.append(msg)

        # version is dealt with above

        elif item['key'] == 'MaturityInformation:Last Update':
            # optional, 1 date
            lastUpdate = item['value'].strip()
            check_is_date(lastUpdate, 'lastUpdate', False, collected_messages)
            log_value(LOGGER, lastUpdate, 'lastUpdate')

        elif item['key'] == 'MaturityInformation:Change Log':
            # optional, multiple strings
            chLog = item['value'].strip()
            check_is_string(chLog, 'change log', False, 1000, collected_messages)
            if len(chLog) > 0:
                changeLogs.append(chLog)
                log_value(LOGGER, chLog, 'changeLog')
            #else:
            #    msg = 'Empty string passed for optional Change Log'
            #    collected_messages.append(msg)

        ### Maturity Information: Done ###

        ### Dependencies Information: ###

        elif item['key'] == 'DependenciesInformation:Required Resources':
            # optional, multiple cv values
            reqRes = item['value'].strip()
            if len(reqRes) > 0:
                requiredResources.append(reqRes)
                log_value(LOGGER, reqRes, 'requiredResource')
            #else:
            #    msg = 'Empty string passed for optional Required Resources'
            #    collected_messages.append(msg)
            # WIP TODO CHECK CV

        elif item['key'] == 'DependenciesInformation:Related Resources':
            # optional, multiple cv values
            relRes = item['value'].strip()
            if len(relRes) > 0:
                relatedResources.append(relRes)
                log_value(LOGGER, relRes, 'relatedResource')
            #else:
            #    msg = 'Empty string passed for optional Related Resources'
            #    collected_messages.append(msg)
            # WIP TODO CHECK CV
    
        elif item['key'] == 'DependenciesInformation:Related Platforms':
            # optional, multiple cv values
            relPlat = item['value'].strip()
            if len(relPlat) > 0:
                relatedPlatforms.append(relPlat)
                log_value(LOGGER, relPlat, 'relatedPlatform')
            #else:
            #    msg = 'Empty string passed for optional Related Platforms'
            #    collected_messages.append(msg)
            # WIP TODO CHECK CV

        elif item['key'] == 'DependenciesInformation:NONE YET TODO WIP':
            # optional, 1 cv value
            # TODO Missing item Catalogue!!
            msg = 'Missing key for Catalogue on Blue-Cloud side yet!'
            collected_messages.append(msg)
            catalogue = item['value'].strip()
            log_value(LOGGER, catalogue, 'catalogue')
            # WIP TODO CHECK CV

        ### Dependencies Information: Done ###

        ### Attribution Information ###

        elif item['key'] == 'AttributionInformation:Funding Body':
            # optional, multiple cv values
            value_bluecloud = item['value'].strip()
            value_eosc = FUNDING_BODIES[value_bluecloud.lower()]
            fundingBodies.append(value_eosc)
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'fundingBody')

        elif item['key'] == 'AttributionInformation:Funding Program':
            # optional, multiple cv values
            value_bluecloud = item['value'].strip()
            value_eosc = FUNDING_PROGRAMS[value_bluecloud.lower()]
            fundingPrograms.append(value_eosc)
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'fundingProgram')

        elif item['key'] == 'AttributionInformation:Project':
            # optional, multiple cv values
            # TODO: I hope this is the correct one, as the key word does not
            # contain the word "grant"
            grantProject = item['value'].strip()
            check_is_string(grantProject, "grantProject", False, 100, collected_messages)
            if len(grantProject) > 0:
                grantProjectNames.append(grantProject)
                log_value(LOGGER, grantProject, 'grantProject')
            #else:
            #    msg = 'Empty string passed for optional Project'
            #    collected_messages.append(msg)

        ### Attribution Information: Done ###

        ### Management Information: ###

        elif item['key'] == 'ManagementInformation:Helpdesk Page':
            # optional, 1 url
            helpdeskPage = item['value'].strip()
            check_is_url(helpdeskPage, 'helpdeskPage', False, collected_messages)
            log_value(LOGGER, helpdeskPage, 'helpdeskPage')

        elif item['key'] == 'ManagementInformation:User Manual':
            # optional, 1 url
            userManual = item['value'].strip()
            check_is_url(userManual, 'userManual', False, collected_messages)
            log_value(LOGGER, userManual, 'userManual')

        elif item['key'] == 'ManagementInformation:Terms Of Use':
            # optional, 1 url
            termsOfUse = item['value'].strip()
            check_is_url(termsOfUse, 'termsOfUse', True, collected_messages)
            log_value(LOGGER, termsOfUse, 'termsOfUse')

        elif item['key'] == 'ManagementInformation:Privacy Policy':
            # optional, 1 url
            privacyPolicy = item['value'].strip()
            check_is_url(privacyPolicy, 'privacyPolicy', True, collected_messages)
            log_value(LOGGER, privacyPolicy, 'privacyPolicy')

        elif item['key'] == 'ManagementInformation:Access Policy':
            # optional, 1 url
            accessPolicy = item['value'].strip()
            check_is_url(accessPolicy, 'accessPolicy', False, collected_messages)
            log_value(LOGGER, accessPolicy, 'accessPolicy')

        elif item['key'] == 'ManagementInformation:Service Level':
            # deprecated
            serviceLevel = item['value'].strip()
            check_is_url(serviceLevel, 'serviceLevel', False, collected_messages)
            log_value(LOGGER, serviceLevel, 'serviceLevel')
            msg = 'Deprecated Service Level ("%s"), should now be Resource Level' % serviceLevel
            collected_messages.append(msg)
 
        elif item['key'] == 'ManagementInformation:Resource Level':
            # optional, 1 url
            resourceLevel = item['value'].strip()
            check_is_url(resourceLevel, 'resourceLevel', False, collected_messages)
            log_value(LOGGER, resourceLevel, 'resourceLevel')

        elif item['key'] == 'ManagementInformation:Training Information':
            # optional, 1 url
            trainingInformation = item['value'].strip()
            check_is_url(trainingInformation, 'trainingInformation', False, collected_messages)
            log_value(LOGGER, trainingInformation, 'trainingInformation')

        elif item['key'] == 'ManagementInformation:Status Monitoring':
            # optional, 1 url
            statusMonitoring = item['value'].strip()
            check_is_url(statusMonitoring, 'statusMonitoring', False, collected_messages)
            log_value(LOGGER, statusMonitoring, 'statusMonitoring')

        elif item['key'] == 'ManagementInformation:Maintenance':
            # optional, 1 url
            maintenance = item['value'].strip()
            check_is_url(maintenance, 'maintenance', False, collected_messages)
            log_value(LOGGER, maintenance, 'maintenance')

        ### Management Information: Done ###

        ### Access and Order Information ###

        elif item['key'] == 'AccessOrderInformation:Order Type':
            # mandatory, 1 CV value
            value_bluecloud = item['value'].strip()

            # TODO REMOVE THIS HACK storm severity
            # Reported to myself! https://support.d4science.org/issues/23185
            # This seems to be a problem at EOSC rather than at Blue-Cloud!
            if value_bluecloud =='Request/Order required':
                msg = 'PROBLEM AT EOSC: Order Type: EOSC is not sure whether this is a valid value: %s' % value_bluecloud
                collected_messages.append(msg)
                # For now for validating we may have to change it manually:
                value_bluecloud = "Order required"
                LOGGER.info('orderType: For now, we are manually changing it to %s' % value_bluecloud)

            value_eosc = ORDER_TYPES[value_bluecloud.lower()]
            orderType = value_eosc
            log_value(LOGGER, '%s" ("%s")' % (value_eosc, value_bluecloud), 'orderType')

        elif item['key'] == 'AccessOrderInformation:Order':
            # optional, 1 url
            order = item['value'].strip()
            check_is_url(order, 'order', False, collected_messages)
            log_value(LOGGER, order, 'order')

        ### Access and Order Information: done ###

        ### Financial Information: ###

        elif item['key'] == 'FinancialInformation:Payment Model':
            # optional, 1 url
            paymentModel = item['value'].strip()
            check_is_url(paymentModel, 'paymentModel', False, collected_messages)
            log_value(LOGGER, paymentModel, 'paymentModel')

        elif item['key'] == 'FinancialInformation:Pricing':
            # optional, 1 url
            pricing = item['value'].strip()
            check_is_url(pricing, 'pricing', False, collected_messages)
            log_value(LOGGER, pricing, 'pricing')

        ### Financial Information: Done ###

    # Finished iterating. We now should have collected info
    # for each metadata item. Now we still need to do some
    # cutting and stitching.



    ############################
    ### Construct multimedia ###
    ############################
    # TODO: EOSC allows several of these pairs. This is only possible if Blue-Cloud stores them
    # as composites too, so we don't match the wrong ones.
    
    if multimedia_url == 'www.mymedia.org':
        # TODO REMOVE THIS HACK:
        # Waiting for: DUMMY FAKE: https://support.d4science.org/issues/23123
        multimedia_url = 'http://dkrz.de'
        msg = 'REPORTED URGENT: replaced field "multimedia": "%s" with "http://dkrz.de! https://support.d4science.org/issues/23123' % item
        LOGGER.error(msg)
        raise ValueError(msg)

    if len(multimedia_url) == 0 and len(multimedia_name) == 0:
        multimedia = []
    else:
        multimedia_composite = [{"multimediaURL": multimedia_url, "multimediaName": multimedia_name}]
    log_value(LOGGER, multimedia_composite, 'multimedia')


    ##########################
    ### Construct useCases ###
    ##########################
    # TODO: EOSC allows several of these pairs. This is only possible if Blue-Cloud stores them
    # as composites too, so we don't match the wrong ones.

    if use_case_url == 'www.ausecase.org':
        # TODO REMOVE THIS HACK:
        # Waiting for: DUMMY FAKE: https://support.d4science.org/issues/23123
        use_case_url = 'http://dkrz.de'
        msg = 'REPORTED URGENT: replaced field "use_case_url": "%s" with "http://dkrz.de! https://support.d4science.org/issues/23123' % item
        LOGGER.error(msg)
        raise ValueError(msg)

    if len(use_case_url) == 0 and len(use_case_name) == 0:
        use_cases_composite = []
    else:
        use_cases_composite = [{"useCaseURL": use_case_url, "useCaseName": use_case_name}]
    log_value(LOGGER, use_cases_composite, 'useCases')

    #############################################
    ### Construct mainContact / publicContact ###
    #############################################

    maincontact_firstName, maincontact_lastName = get_name_from_val(maincontact_name, 'maincontact_name', collected_messages)
    publiccontact_firstName, publiccontact_lastName = get_name_from_val(publiccontact_name, 'publiccontact_name', collected_messages)
    check_is_string(publiccontact_firstName, 'publiccontact_firstName', False, 20, collected_messages)
    check_is_string(publiccontact_lastName, 'publiccontact_lastName', False, 20, collected_messages)
    check_is_string(maincontact_firstName, 'maincontact_firstName', True, 20, collected_messages)
    check_is_string(maincontact_lastName, 'maincontact_lastName', True, 20, collected_messages)


    #####################
    ### Match domains ###
    #####################
    # Why? BlueCloud lists them loosely, but EOSC wants them in a composite.
    # If only one pair is passed, this would be easy, but we cannot be sure of that.

    composite_domains = []
    used_domids = []
    LOGGER.debug('All %s found domains: %s' % (len(domain_ids), domain_ids))
    LOGGER.debug('All %s found subdomains: %s' % (len(subdomain_ids), subdomain_ids))
    for subdom_id in subdomain_ids:
        maindom_id = CV_DOM_MAPPING[subdom_id]
        if maindom_id in domain_ids:
            used_domids.append(maindom_id)
            LOGGER.debug('Subdomain "%s" has main domain "%s"' % (subdom_id, maindom_id))
            composite = {
                "scientificDomain": maindom_id,
                "scientificSubdomain": subdom_id,
            }
            composite_domains.append(composite)
        else:
            LOGGER.error('REPORTED PROBLEM: Did not find domain "%s" in metadata (to match subdomain "%s". https://support.d4science.org/issues/23155' % (maindom_id, subdom_id))
            LOGGER.warning('REPORTED HACK: Assigning subdom "%s" with dom "%s" because they are the only domains. This will fail validation.' % (subdom_id, maindom_id))

            if len(domain_ids) == 1 and len(subdomain_ids)==1:
                composite = {
                    "scientificDomain": domain_ids[0],
                    "scientificSubdomain": subdomain_ids[0],
                }
                composite_domains.append(composite)

    for tmp_id in domain_ids:
        if tmp_id not in used_domids:
            LOGGER.error('(not occurring? not reported) This domain was present but without a subdomain! Every domain needs a subdomain: %s' % tmp_id)

    for tmp in composite_domains:
        log_value(LOGGER, tmp, 'scientificDomain')



    ########################
    ### Match categories ###
    ########################
    # Why? BlueCloud lists them loosely, but EOSC wants them in a composite.
    # If only one pair is passed, this would be easy, but these services pass several categories:
    # * zoo_and_phytoplankton_essential_ocean_variable_products_vlab
    # Also, that service has 5 categories and 9 subcategories, leading to 9 

    composite_categories = []
    used_mainids = []
    LOGGER.debug('All %s found categories: %s' % (len(category_ids), category_ids))
    LOGGER.debug('All %s found subcategories: %s' % (len(subcategory_ids), subcategory_ids))
    for subcat_id in subcategory_ids:
        maincat_id = CV_CAT_MAPPING[subcat_id]
        if maincat_id in category_ids:
            used_mainids.append(maincat_id)
            LOGGER.debug('Subcategory "%s" has main category "%s"' % (subcat_id, maincat_id))
            composite = {
                "category": maincat_id,
                "subcategory": subcat_id,
            }
            composite_categories.append(composite)
        else:
            LOGGER.error('Did not find category "%s" in metadata (to match subcategory "%s".' % (maincat_id, subcat_id))
            LOGGER.warning('Assigning subcat "%s" with cat "%s" because they are the only categories. This will fail validation.' % (subcat_id, maincat_id))
            if len(category_ids) == 1 and len(subcategory_ids)==1:
                composite = {
                    "category": category_ids[0],
                    "subcategory": subcategory_ids[0],
                }
                composite_categories.append(composite)

    for tmp_id in category_ids:
        if tmp_id not in used_mainids:
            LOGGER.error('This category was present but without a subcategory! Every category needs a subcategory: %s' % tmp_id)

    for tmp in composite_categories:
        log_value(LOGGER, tmp, 'category')


    ###################
    ### Filter tags ###
    ###################
    # Filtering redundant tags, as agreed with Leonardo Candela
    # See: https://support.d4science.org/issues/23181

    new_tags = []
    removed = []
    for item in tags:
        if item in targetUsersNames:
            removed.append(item)
        elif item.startswith('Access Mode') or item.startswith('Access Type'):
            removed.append(item)
        elif item in category_names or item in domain_names:
            removed.append(item)
        else:
            new_tags.append(item)

    if not len(tags) == len(new_tags):
        LOGGER.debug('Removed some tags! Before: %s, now: %s (left: %s, removed: %s)' % (len(tags), len(new_tags), new_tags, removed))
        tags = new_tags

    for tag in tags:
        check_is_string(tag, 'tags', False, 50, collected_messages)
        log_value(LOGGER, tag, 'tag')


    #########################
    ### Check for missing ###
    #########################

    missing_mandatory_items = []

    # id: TODO
    if abbreviation is None or len(abbreviation.strip()) == 0:
        missing_mandatory_items.append('abbreviation')
    if eosc_name is None or len(eosc_name.strip()) == 0:
        missing_mandatory_items.append('eosc_name')
    if resourceOrganisation is None or len(resourceOrganisation.strip()) == 0:
        missing_mandatory_items.append('resourceOrganisation')
    if webpage is None or len(webpage.strip()) == 0:
        missing_mandatory_items.append('webpage')
    if description is None or len(description.strip()) == 0:
        missing_mandatory_items.append('description')
    if tagline is None or len(tagline.strip()) == 0:
        missing_mandatory_items.append('tagline')
    if logo is None or len(logo.strip()) == 0:
        missing_mandatory_items.append('logo')

    # Composites:
    for item in composite_domains:
        if item['scientificDomain'] is None or len(item['scientificDomain'].strip()) == 0:
            missing_mandatory_items.append('scientificDomain')
        if item['scientificSubdomain'] is None or len(item['scientificSubdomain'].strip()) == 0:
            missing_mandatory_items.append('scientificSubdomain')

    for item in composite_categories:
        if item['category'] is None or len(item['category'].strip()) == 0:
            missing_mandatory_items.append('category')
        if item['subcategory'] is None or len(item['subcategory'].strip()) == 0:
            missing_mandatory_items.append('subcategory')

    # Lists:
    if len(targetUsers) == 0:
        missing_mandatory_items.append('targetUsers')
        # No need to check each item, as they come from a CV.

    for item in geographicalAvailabilities:
        if item is None or len(item) == 0:
            missing_mandatory_items.append('geographicalAvailabilities')

    for item in languageAvailabilities:
        if item is None or len(item) == 0:
            missing_mandatory_items.append('languageAvailabilities')

    if len(missing_mandatory_items) > 0:
        LOGGER.warning('These are mandatory but missing: %s' % missing_mandatory_items)
    else:
        LOGGER.info('No mandatory items are missing.')

    ################################
    ### Print collected messags: ###
    ################################

    LOGGER.warning('  ******* Collected messages: *******')
    for msg in collected_messages:
        LOGGER.warning('  * '+msg)
    LOGGER.warning('  ***********************************')

    # WIP ANY OTHER??




    # TODO Doeppelt
    #if not scientificSubdomain in CV_DOM_MAPPING[scientificDomain]:
    #    LOGGER.error("Domains don't match: %s not in %s" % (scientificSubdomain, scientificDomain)) 


    ####################################
    ### Constructing the EOSC format ###
    ####################################

    target = {
        "blue_id": blue_id,
        "abbreviation": abbreviation,
        "name": eosc_name,
        "resourceOrganisation": resourceOrganisation,
        "resourceProviders": resourceProviders,
        "webpage": webpage,
        "description": description,
        "tagline": tagline,
        "logo": logo,
        "multimedia": multimedia_composite,
        "useCases": use_cases_composite,
        "scientificDomains": composite_domains,
        "categories": composite_categories,
        "targetUsers": targetUsers,
        "accessTypes": accessTypes,
        "accessModes": accessModes,
        "tags": tags,
        "geographicalAvailabilities": geographicalAvailabilities,
        "languageAvailabilities": languageAvailabilities,
        "resourceGeographicLocations": resourceGeographicLocations,
        "mainContact": {
            "firstName": maincontact_firstName,
            "lastName": maincontact_lastName,
            "email": maincontact_email,
            "phone": maincontact_phone,
            "position": maincontact_position,
            "organisation": maincontact_organisation
        },
        "publicContacts": [{
            "firstName": publiccontact_firstName,
            "lastName": publiccontact_lastName,
            "email": publiccontact_email,
            "phone": publiccontact_phone,
            "position": publiccontact_position,
            "organisation": publiccontact_organisation
        }],
        "helpdeskEmail": helpdeskEmail,
        "securityContactEmail": securityContactEmail,
        "trl": trl,
        "lifeCycleStatus": lifeCycleStatus,
        "certifications": certifications,
        "standards": standards,
        "openSourceTechnologies": openSourceTechnologies,
        "version": version,
        "lastUpdate": lastUpdate,
        "changeLog": changeLogs,
        "requiredResources": requiredResources,
        "relatedResources": relatedResources,
        "relatedPlatforms": relatedPlatforms,
        "fundingBody": fundingBodies,
        "fundingPrograms": fundingPrograms,
        "grantProjectNames": grantProjectNames,
        "helpdeskPage": helpdeskPage,
        "userManual": userManual,
        "termsOfUse": termsOfUse,
        "privacyPolicy": privacyPolicy,
        "accessPolicy": accessPolicy,
        "serviceLevel": serviceLevel,
        "trainingInformation": trainingInformation,
        "statusMonitoring": statusMonitoring,
        "maintenance": maintenance,
        "orderType": orderType,
        "order": order,
        "paymentModel": paymentModel,
        "pricing": pricing
    }

    return target

