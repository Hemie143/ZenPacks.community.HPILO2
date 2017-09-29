##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

__doc__ = """

Plugin to get the basic information about the HP Proliant Server

"""
__version__ = '$Revision: $'[11:-2]
import logging
log = logging.getLogger('zen.HPPluginBase')

import cPickle as pickle
from Products.DataCollector.plugins.DataMaps import RelationshipMap


class HPPluginBase(object):
    """Base class for modeler plugins with convenience methods"""
    # whether to save data for testing
    deviceProperties = ('zILO2CollectSamples',)

    def get_rel_maps(self, comp_maps, relname, meta_type):
        maps = []
        for compname, compmaps in comp_maps.items():
            maps.append(RelationshipMap(relname=relname,
                                        compname=compname,
                                        modname='ZenPacks.community.HPILO2.{}'.format(meta_type),
                                        objmaps=compmaps))
        return maps


    def get_maps(self, maps, compname, relname, meta_type):
        return RelationshipMap(relname=relname,
                               compname=compname,
                               modname='ZenPacks.community.HPILO2.{}'.format(meta_type),
                               objmaps=maps)
    """
    def write_test_data(self, filename, results):
        file = open('/tmp/{}.pickle'.format(filename), 'wb+')
        pickle.dump(results, file)
        file.close()

    def write_test_txt(self, filename, lines):
        file = open('/tmp/{}.txt'.format(filename), 'wb+')
        file.writelines(lines)
        file.close()

    def fix_objectmap_attr_wtspc(self, objmap):
        '''remove extra whitespace from string attributes'''
        for k, v in objmap.items():
            val = getattr(objmap, k)
            if not val: continue
            if type(val) != str: continue
            setattr(objmap, k, v.strip())
        return objmap

    def fix_objectmap_attr_na(self, objmap):
        ''' Remove attributes with 'N/A' value
            Fixes ZEN-22605
        '''
        for k, v in objmap.items():
            val = getattr(objmap, k)
            if not val: continue
            if type(val) != str: continue
            if val == 'N\A':
                delattr(objmap, k)
        return objmap

    def fix_whtspc_maps(self, maps):
        '''remove extra whitespace from string attributes'''
        for map in maps:
            if map.__class__.__name__ == 'ObjectMap':
                map = self.fix_objectmap_attr_wtspc(map)
            elif map.__class__.__name__ == 'RelationshipMap':
                for objmap in map.maps:
                    objmap = self.fix_objectmap_attr_wtspc(objmap)
        return maps

    def fix_na_maps(self, maps):
        '''ensure that N/A values are removed from object maps'''
        for map in maps:
            if map.__class__.__name__ == 'ObjectMap':
                map = self.fix_objectmap_attr_na(map)
            elif map.__class__.__name__ == 'RelationshipMap':
                for objmap in map.maps:
                    objmap = self.fix_objectmap_attr_na(objmap)
        return maps

    def uniq_maps(self, maps):
        '''ensure that duplicate components are not returned'''
        for relmap in maps:
            if relmap.__class__.__name__ != 'RelationshipMap':
                continue
            ids = []
            uniqs = []
            for objmap in relmap.maps:
                if objmap.id not in ids:
                    ids.append(objmap.id)
                    uniqs.append(objmap)
            relmap.maps = uniqs
        return maps

    def fix_object_maps(self, maps):
        '''ensure that N/A values are removed from object maps
            Fixes ZEN-22605
        '''
        for relmap in maps:
            if relmap.__class__.__name__ != 'RelationshipMap':
                continue
            objmaps = []
            for objmap in relmap.maps:
                for k, v in objmap.items():
                    if v == 'N/A':
                        delattr(objmap, k)
                objmaps.append(objmap)
            relmap.maps = objmaps
        return maps

    def fix_id_maps(self, maps):
        '''ensure that object maps with blank ids'''
        for map in maps:
            if map.__class__.__name__ == 'ObjectMap':
                continue
            elif map.__class__.__name__ == 'RelationshipMap':
                objmaps = []
                for objmap in map.maps:
                    if getattr(objmap, 'id', '') == '':
                        continue
                    objmaps.append(objmap)
                map.maps = objmaps
        return maps

    def fix_maps(self, maps):
        '''wrapper around all plugin result maps fixes'''
        maps = self.fix_id_maps(maps)
        maps = self.uniq_maps(maps)
        maps = self.fix_whtspc_maps(maps)
        maps = self.fix_na_maps(maps)
        return maps
    """