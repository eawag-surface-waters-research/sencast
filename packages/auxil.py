#! /usr/bin/env python
# coding: utf8

import configparser
import getpass
import os
import socket
import xml.etree.cElementTree as ElementTree


# The name of the folder to which the output product will be saved
IDEPIX_OUT_DIR = "L1P"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
IDEPIX_NAME = "L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
IDEPIX_QL_OUT_DIR = "L1P-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
IDEPIX_QL_NAME = "L1P_reproj_{}_{}.png"

# The name of the folder to which the output product will be saved
C2RCC_OUT_DIR = "L2C2RCC"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
C2RCC_NAME = "L2C2RCC_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
C2RCC_QL_OUT_DIR = "L2C2RCC-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
C2RCC_QL_NAME = "L2C2RCC_L1P_reproj_{}_{}.png"

# The name of the folder to which the output product will be saved
POLY_OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
POLY_NAME = "L2POLY_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
POLY_QL_OUT_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
POLY_QL_NAME = "L2POLY_L1P_reproj_{}_{}.png"

# The name of the folder to which the output product will be saved
MPH_OUT_DIR = "L2MPH"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
MPH_NAME = "L2MPH_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
MPH_QL_OUT_DIR = "L2MPH-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
MPH_QL_NAME = "L2MPH_L1P_reproj_{}_{}.png"


def gpt_xml(operator, product_parameters, xml_path):

    graph = ElementTree.Element('graph')

    ###########################################
    # REPROJECT
    # create Reproject node elements
    if operator == 'Reproject':
        graph.set('id', 'Reproj')
        version = ElementTree.SubElement(graph, 'version')
        reproj_node = ElementTree.SubElement(graph, 'node', id='reprojNode')
        op = ElementTree.SubElement(reproj_node, 'operator')
        sources = ElementTree.SubElement(reproj_node, 'sources')
        sourceProduct = ElementTree.SubElement(sources, 'source')
        parameters = ElementTree.SubElement(reproj_node, 'parameters')
        crs = ElementTree.SubElement(parameters, 'crs')
        resampling = ElementTree.SubElement(parameters, 'resampling')
        referencePixelX = ElementTree.SubElement(parameters, 'referencePixelX')
        referencePixelY = ElementTree.SubElement(parameters, 'referencePixelY')
        easting = ElementTree.SubElement(parameters, 'easting')
        northing = ElementTree.SubElement(parameters, 'northing')
        pixelSizeX = ElementTree.SubElement(parameters, 'pixelSizeX')
        pixelSizeY = ElementTree.SubElement(parameters, 'pixelSizeY')
        width = ElementTree.SubElement(parameters, 'width')
        height = ElementTree.SubElement(parameters, 'height')
        orthorectify = ElementTree.SubElement(parameters, 'orthorectify')
        noDataValue = ElementTree.SubElement(parameters, 'noDataValue')
        includeTiePointGrids = ElementTree.SubElement(parameters, 'includeTiePointGrids')
        addDeltaBands = ElementTree.SubElement(parameters, 'addDeltaBands')

        # specify Reproject elements
        version.text = '1.0'
        op.text = 'Reproject'
        sourceProduct.text = '${sourceProduct}'
        crs.text = 'EPSG:4326'
        resampling.text = 'Nearest'
        referencePixelX.text = '0'
        referencePixelY.text = '0'
        easting.text = product_parameters['easting']
        northing.text = product_parameters['northing']
        pixelSizeX.text = product_parameters['pixelSizeX']
        pixelSizeY.text = product_parameters['pixelSizeY']
        width.text = product_parameters['width']
        height.text = product_parameters['height']
        orthorectify.text = 'false'
        noDataValue.text = 'NaN'
        includeTiePointGrids.text = 'true'
        addDeltaBands.text = 'false'

    ###########################################
    # IDEPIX
    # create and specify general Idepix elements
    if operator.startswith('Idepix'):
        graph.set('id', 'idepix')
        version = ElementTree.SubElement(graph, 'version')
        idepix_node = ElementTree.SubElement(graph, 'node', id='idepixNode')
        idepix_op = ElementTree.SubElement(idepix_node, 'operator')
        sources = ElementTree.SubElement(idepix_node, 'sources')
        sourceProduct = ElementTree.SubElement(sources, 'sourceProduct')
        parameters = ElementTree.SubElement(idepix_node, 'parameters')
        computeCloudBuffer = ElementTree.SubElement(parameters, 'computeCloudBuffer')
        cloudBufferWidth = ElementTree.SubElement(parameters, 'cloudBufferWidth')
        version.text = '1.0'
        idepix_op.text = operator
        sourceProduct.text = '${sourceProduct}'
        computeCloudBuffer.text = 'false'

        # create and specify S2 Idepix specific elements (first part of condition only for backward compatibility)
        if "Sentinel2" in operator or "S2" in operator:
            copyToaReflectances = ElementTree.SubElement(parameters, 'copyToaReflectances')
            copyFeatureValues = ElementTree.SubElement(parameters, 'copyFeatureValues')
            computeMountainShadow = ElementTree.SubElement(parameters, 'computeMountainShadow')
            computeCloudShadow = ElementTree.SubElement(parameters, 'computeCloudShadow')
            computeCloudBufferForCloudAmbiguous = ElementTree.SubElement(parameters, 'computeCloudBufferForCloudAmbiguous')
            demName = ElementTree.SubElement(parameters, 'demName')
            copyToaReflectances.text = 'true'
            copyFeatureValues.text = 'false'
            computeMountainShadow.text = 'true'
            # Calculating cloud shadows with reprojected data in degree units gives terrible errors:
            # java.lang.IllegalArgumentException: Width (-329182666) and height (-329182666) must be > 0
            computeCloudShadow.text = 'false'
            computeCloudBufferForCloudAmbiguous.text = 'true'
            demName.text = 'SRTM 3Sec'
            cloudBufferWidth.text = '5'

        # create and specify S2 Idepix specific elements (first part of condition only for backward compatibility)
        elif "Sentinel3" in operator or "Olci" in operator:
            radianceBandsToCopy = ElementTree.SubElement(parameters, 'radianceBandsToCopy')
            reflBandsToCopy = ElementTree.SubElement(parameters, 'reflBandsToCopy')
            outputSchillerNNValue = ElementTree.SubElement(parameters, 'outputSchillerNNValue')
            useSrtmLandWaterMask = ElementTree.SubElement(parameters, 'useSrtmLandWaterMask')
            radianceBandsToCopy.text = 'Oa01_radiance,Oa02_radiance,Oa03_radiance,Oa04_radiance,Oa05_radiance,' \
                                       'Oa06_radiance,Oa07_radiance,Oa08_radiance,Oa09_radiance,Oa10_radiance,' \
                                       'Oa11_radiance,Oa12_radiance,Oa13_radiance,Oa14_radiance,Oa15_radiance,' \
                                       'Oa16_radiance,Oa17_radiance,Oa18_radiance,Oa19_radiance,Oa20_radiance,' \
                                       'Oa21_radiance'
            reflBandsToCopy.text = 'Oa01_reflectance,Oa02_reflectance,Oa03_reflectance,Oa04_reflectance,' \
                                   'Oa05_reflectance,Oa06_reflectance,Oa07_reflectance,Oa08_reflectance,' \
                                   'Oa09_reflectance,Oa10_reflectance,Oa11_reflectance,Oa12_reflectance,' \
                                   'Oa13_reflectance,Oa14_reflectance,Oa15_reflectance,Oa16_reflectance,' \
                                   'Oa17_reflectance,Oa18_reflectance,Oa19_reflectance,Oa20_reflectance,' \
                                   'Oa21_reflectance'
            outputSchillerNNValue.text = 'false'
            useSrtmLandWaterMask.text = 'true'
            cloudBufferWidth.text = '2'

    ###########################################
    # C2RCC
    # create C2RCC elements
    if operator.startswith('c2rcc'):
        graph.set('id', 'c2rcc')
        version = ElementTree.SubElement(graph, 'version')
        c2rcc_node = ElementTree.SubElement(graph, 'node', id='c2rccNode')
        c2rcc_op = ElementTree.SubElement(c2rcc_node, 'operator')
        sources = ElementTree.SubElement(c2rcc_node, 'sources')
        sourceProduct = ElementTree.SubElement(sources, 'sourceProduct')
        parameters = ElementTree.SubElement(c2rcc_node, 'parameters')
        validPixelExpression = ElementTree.SubElement(parameters, 'validPixelExpression')
        salinity = ElementTree.SubElement(parameters, 'salinity')
        temperature = ElementTree.SubElement(parameters, 'temperature')
        ozone = ElementTree.SubElement(parameters, 'ozone')
        press = ElementTree.SubElement(parameters, 'press')
        TSMfakBpart = ElementTree.SubElement(parameters, 'TSMfakBpart')
        TSMfakBwit = ElementTree.SubElement(parameters, 'TSMfakBwit')
        CHLexp = ElementTree.SubElement(parameters, 'CHLexp')
        CHLfak = ElementTree.SubElement(parameters, 'CHLfak')
        thresholdRtosaOOS = ElementTree.SubElement(parameters, 'thresholdRtosaOOS')
        thresholdAcReflecOos = ElementTree.SubElement(parameters, 'thresholdAcReflecOos')
        thresholdCloudTDown865 = ElementTree.SubElement(parameters, 'thresholdCloudTDown865')
        alternativeNNPath = ElementTree.SubElement(parameters, 'alternativeNNPath')
        outputAsRrs = ElementTree.SubElement(parameters, 'outputAsRrs')
        deriveRwFromPathAndTransmittance = ElementTree.SubElement(parameters, 'deriveRwFromPathAndTransmittance')
        if 'msi' not in operator:
            useEcmwfAuxData = ElementTree.SubElement(parameters, 'useEcmwfAuxData')
            useEcmwfAuxData.text = 'true'
        outputRtoa = ElementTree.SubElement(parameters, 'outputRtoa')
        outputRtosaGc = ElementTree.SubElement(parameters, 'outputRtosaGc')
        outputRtosaGcAann = ElementTree.SubElement(parameters, 'outputRtosaGcAann')
        outputRpath = ElementTree.SubElement(parameters, 'outputRpath')
        outputTdown = ElementTree.SubElement(parameters, 'outputTdown')
        outputTup = ElementTree.SubElement(parameters, 'outputTup')
        outputAcReflectance = ElementTree.SubElement(parameters, 'outputAcReflectance')
        outputRhown = ElementTree.SubElement(parameters, 'outputRhown')
        outputOos = ElementTree.SubElement(parameters, 'outputOos')
        outputKd = ElementTree.SubElement(parameters, 'outputKd')
        outputUncertainties = ElementTree.SubElement(parameters, 'outputUncertainties')
        # specify C2RCC elements
        version.text = '1.0'
        c2rcc_op.text = operator
        sourceProduct.text = '${sourceProduct}'
        validPixelExpression.text = product_parameters.get('validPixelExpression')
        salinity.text = '0.05'
        temperature.text = '15.0'
        ozone.text = '330.0'        # str(product_parameters.get('ozone'))
        press.text = '1000.0'       # str(product_parameters.get('press'))
        TSMfakBpart.text = '1.72'
        TSMfakBwit.text = '3.1'
        CHLexp.text = '1.04'
        CHLfak.text = '21.0'
        thresholdRtosaOOS.text = '0.05'
        thresholdAcReflecOos.text = '0.1'
        thresholdCloudTDown865.text = '0.955'
        alternativeNNPath.text = product_parameters.get('alternativeNNPath')
        outputAsRrs.text = 'false'
        deriveRwFromPathAndTransmittance.text = 'false'
        outputRtoa.text = 'true'
        outputRtosaGc.text = 'false'
        outputRtosaGcAann.text = 'false'
        outputRpath.text = 'false'
        outputTdown.text = 'false'
        outputTup.text = 'false'
        outputAcReflectance.text = 'true'
        outputRhown.text = 'true'
        outputOos.text = 'false'
        outputKd.text = 'true'
        outputUncertainties.text = 'true'

    # create NetCDF writer elements
    write_node = ElementTree.SubElement(graph, 'node', id='writeNode')
    write_op = ElementTree.SubElement(write_node, 'operator')
    write_sources = ElementTree.SubElement(write_node, 'sources')
    write_source = ElementTree.SubElement(write_sources, 'source')
    write_parameters = ElementTree.SubElement(write_node, 'parameters')
    file = ElementTree.SubElement(write_parameters, 'file')
    formatName = ElementTree.SubElement(write_parameters, 'formatName')

    # specify NetCDF writer elements
    write_op.text = 'Write'
    if operator.startswith('c2rcc'):
        write_source.text = 'c2rccNode'
    elif operator.startswith('Idepix'):
        write_source.text = 'idepixNode'
    elif operator == 'Reproject':
        write_source.text = 'reprojNode'
    file.text = '${targetProduct}'
    formatName.text = 'NetCDF-BEAM'

    xml = open(xml_path, 'wb')
    tree = ElementTree.ElementTree(graph)
    tree.write(xml)
    xml.close()


def load_environment(env_file=None, env_path="environments"):
    env = configparser.ConfigParser()

    # Try to use provided env file
    if env_file and not os.path.isabs(env_file):
        env_file = os.path.join(env_path, env_file)
        if not os.path.isfile(env_file):
            raise RuntimeError("The evironment file could not be found: {}".format(env_file))
        env.read(env_file)
        return env

    # Try to use host and user specific env file
    host_user_env_file = os.path.join(env_path, "{}.{}.ini".format(socket.gethostname(), getpass.getuser()))
    if os.path.isfile(host_user_env_file):
        env.read(host_user_env_file)
        return env

    # Try to use host specific env file
    host_env_file = os.path.join(env_path, "{}.ini".format(socket.gethostname()))
    if os.path.isfile(host_env_file):
        env.read(host_env_file)
        return env

    raise RuntimeError("Could not load any of the following evironments:\n{}\n{}".format(host_user_env_file, host_env_file))


def load_params(params_file, params_path=None):
    if params_path and not os.path.isabs(params_file):
        params_file = os.path.join(params_path, params_file)
    if not os.path.isfile(params_file):
        raise RuntimeError("The parameter file could not be found: {}".format(params_file))
    params = configparser.ConfigParser()
    params.read(params_file)
    return params


def load_wkt(wkt_file, wkt_path=None):
    if wkt_path and not os.path.isabs(wkt_file):
        wkt_file = os.path.join(wkt_path, wkt_file)
    if not os.path.isfile(wkt_file):
        raise RuntimeError("The wkt file could not be found: {}".format(wkt_file))
    with open(wkt_file, "r") as file:
        return file.read()


def init_out_paths(out_root_path, params):
    name, wkt = params['General']['name'], params['General']['wkt'].split(".")[0]
    start, end = params['General']['start'][:10], params['General']['end'][:10]
    out_path = os.path.join(out_root_path, "{}_{}_{}_{}".format(name, wkt, start, end))

    # idepix output folder
    print("Creating IdePix L1P directory")
    idepix_path = os.path.join(out_path, IDEPIX_OUT_DIR)
    os.makedirs(idepix_path, exist_ok=True)
    print("Creating IdePix map directories")
    qlrgb_path = os.path.join(out_path, IDEPIX_QL_OUT_DIR.format("rgb"))
    os.makedirs(qlrgb_path, exist_ok=True)
    qlfc_path = os.path.join(out_path, IDEPIX_QL_OUT_DIR.format("fc"))
    os.makedirs(qlfc_path, exist_ok=True)

    # c2rcc output folder
    print("Creating C2RCC L2 directory")
    c2rcc_path = os.path.join(out_path, C2RCC_OUT_DIR)
    os.makedirs(c2rcc_path, exist_ok=True)
    print("Creating C2RCC map directories")
    c2rcc_band_paths = {}
    for band in params['C2RCC_QL']['bands'].split(","):
        c2rcc_band_paths[band] = os.path.join(out_path, C2RCC_QL_OUT_DIR.format(band))
        os.makedirs(c2rcc_band_paths[band], exist_ok=True)

    # polymer output folder
    print("Creating Polymer L2 directory")
    polymer_path = os.path.join(out_path, POLY_OUT_DIR)
    os.makedirs(polymer_path, exist_ok=True)
    print("Creating Polymer map directories")
    polymer_band_paths = {}
    for band in params['POLY_QL']['bands'].split(","):
        polymer_band_paths[band] = os.path.join(out_path, POLY_QL_OUT_DIR.format(band))
        os.makedirs(polymer_band_paths[band], exist_ok=True)

    # mph output folder
    print("Creating MPH L2 directory")
    mph_path = os.path.join(out_path, MPH_OUT_DIR)
    os.makedirs(mph_path, exist_ok=True)
    print("Creating MPH map directories")
    mph_band_paths = {}
    for band in params['MPH_QL']['bands'].split(","):
        mph_band_paths[band] = os.path.join(out_path, MPH_QL_OUT_DIR.format(band))
        os.makedirs(mph_band_paths[band], exist_ok=True)

    return {
        'out_path': out_path,
        'idepix_path': idepix_path,
        'qlfc_path': qlfc_path,
        'qlrgb_path': qlrgb_path,
        'c2rcc_path': c2rcc_path,
        'c2rcc_band_paths': c2rcc_band_paths,
        'poly_path': polymer_path,
        'poly_band_paths': polymer_band_paths,
        'mph_path': mph_path,
        'mph_band_paths': mph_band_paths
    }
