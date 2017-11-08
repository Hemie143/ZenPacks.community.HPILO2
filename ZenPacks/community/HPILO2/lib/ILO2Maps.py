##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
# master dictionary for object maps
# TODO: Remove this ObjectMap mapping, probably not required
ARCH_MAP = { 'HPILO2Chassis': {'totalRam': None,
                               'enclosure': None,
                               'productId': None,
                               'productName': None,
                               'serialNo': None},
             'HPILO2SystemBoard': {'productName': None,
                                   'romVer': None,
                                   'serialNo': None,
                                   },
             'HPILO2ManagementController': {'firmware': None,
                                            'firmwareDate': None,
                                            'ipv4Address': None,
                                            'licenseType': None,
                                            },
             'HPILO2Processor': {'cacheSizeL1': None,
                                 'cacheSizeL2': None,
                                 'cacheSizeL3': None,
                                 'coreCount': None,
                                 'hyperThread': None,
                                 'model': None,
                                 'threadCount': None
                                 },
             'HPILO2Memory': {'size': None,
                              'speed': None,
                              },
             'HPILO2CoolingFan': {'zone': None,
                              },
             'HPILO2Temperature': {'location': None,
                                   'caution': None,
                                   'critical': None
                              },
             'HPILO2PowerSupply': {'status': None,
                              },
             'HPILO2Enclosure': {'firmware': None,
                                 'enclosure_addr': None
                              },
             'HPILO2PhysicalDrive': {'enclosure': None,
                                     'bayIndex': None,
                                     'productId': None,
                                     'driveStatus': None,
                                     'uid_led': None
                              },
             'HPILO2LogicalDrive': {
                              },
             'HPILO2NetworkInterface': {'port': None,
                                        'mac': None,
                              },
             'HPILO2PCIDevice': {'type': None,
                                 'width': None,
                              },
             }

'''
def check_map(ob_map, ob_type):
    """find attributes missing from object map"""
    for k in ARCH_MAP[ob_type].keys():
        if not hasattr(ob_map, k):
            print "%s is missing attribute: %s" % (ob_type, k)
    return ob_map

def clean_map(ob_map, ob_type):
    """find undefined attributes on the object map"""
    for k, v in ob_map.items():
        if k in ['title', 'id', 'snmpindex']: continue
        if k not in ARCH_MAP[ob_type].keys():
            print "%s has undefined attribute: %s" % (ob_type, k)
    return ob_map

def check_empty_map(ob_map, ob_type):
    """find undefined attributes on the object map"""
    for k, v in ob_map.items():
        if v is None:
            print "%s: %s is %s" % (ob_type, k, str(v))
    return ob_map

def fix_map(ob_map, ob_type):
    check_map(ob_map, ob_type)
    clean_map(ob_map, ob_type)
    check_empty_map(ob_map, ob_type)
'''

def get_object_map(ob_type):
    """ Return an empty dictionary for use 
        in an ObjectMap
    """
    return ARCH_MAP[ob_type].copy()
