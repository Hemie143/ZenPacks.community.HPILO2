
# stdlib imports
# Twisted imports
from twisted.internet.defer import DeferredSemaphore, DeferredList, inlineCallbacks, returnValue

# Zenoss imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import MultiArgs
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId

from ZenPacks.community.HPILO2.lib.ILO2XMLParser import ILO2XMLParser
from ZenPacks.community.HPILO2.lib.ILO2ProtocolHandler import ILO2ProtocolHandler
from ZenPacks.community.HPILO2.lib.ILO2Maps import get_object_map
from ZenPacks.community.HPILO2.modeler.HPPluginBase import HPPluginBase

from ZenPacks.community.HPILO2.lib.utils import iterparse

def get_cmd(cmd='GET_EMBEDDED_HEALTH', tag='SERVER_INFO'):
    '''return formatted RIBCL command'''
    return '<{} MODE=\"read\"><{}/></{}>'.format(tag, cmd, tag)

class HPILO2Modeler(HPPluginBase, PythonPlugin):
    deviceProperties = HPPluginBase.deviceProperties + \
        PythonPlugin.deviceProperties + \
        ('zILO2UserName', 'zILO2Password', 'zILO2UseSSL', 'zILO2Port', 'zCollectorClientTimeout')
    # version = 3
    parser = ILO2XMLParser()

    serverDetails = [
        get_cmd('GET_SERVER_NAME'),
        get_cmd('GET_EMBEDDED_HEALTH'),
        get_cmd('GET_HOST_DATA'),
        get_cmd('GET_FW_VERSION', tag='RIB_INFO'),
        ]

    @inlineCallbacks
    def collect(self, device, log):
        log.info('Collecting for {}'.format(device.id))

        if not self.serverDetails:
            log.error('No serverDetails defined in plugin.')
            returnValue(None)

        if not device.zILO2UserName or device.zILO2UserName == '':
            log.warn('ILO User Name is empty')
            log.warn('Wrong username/password')

        if not device.zILO2Password or device.zILO2Password == '':
            log.warn('ILO Password is empty')
            log.warn('Wrong username/password')

        client = ILO2ProtocolHandler(device.manageIp,
                                    device.zILO2Port,
                                    device.zILO2UserName,
                                    device.zILO2Password,
                                    device.zILO2UseSSL,
                                    device.zCollectorClientTimeout)
        deferreds = []
        sem = DeferredSemaphore(1)
        for serverDetail in self.serverDetails:
            d = sem.run(client.send_command, serverDetail)
            deferreds.append(d)

        results = yield DeferredList(deferreds, consumeErrors=True)
        for success, result in results:
            if not success:
                log.error("%s: %s", device.id, result.getErrorMessage())
                returnValue(None)
        returnValue(results)

    def process(self, device, results, log):
        log.info('Processing {} for device {}'.format(self.name(), device.id))
        #log.info('Results:{}'.format(results))

        self.ilo_ipaddr = None
        self.total_mem = 0

        maps = []

        result_data = {}
        for status, result in results:
            parsed = self.parser.parse(result)
            result_data.update(parsed)

        self.server_name = result_data.get('SERVER_NAME', {}).get('VALUE')
        # this means we didn't get good output
        if not self.server_name:
            return maps

        self.host_data = result_data.get('GET_HOST_DATA', {})
        self.fw_data = result_data.get('GET_FW_VERSION', {})
        self.health_data = result_data.get('GET_EMBEDDED_HEALTH_DATA', {})
        self.glance_data = self.parser.get_merged(self.get_health_data_section('HEALTH_AT_A_GLANCE'))

        log.debug('***HOST_DATA***:{}'.format(self.host_data))

        # get some global info we can use throughout
        self.get_product_serial()
        self.get_ilo_info()
        self.get_chassis_mem(log)

        if len(self.host_data) == 0:
            log.warning('Command "{}" returned no output'.format('GET_HOST_DATA'))
            return
        if len(self.fw_data) == 0:
            log.warning('Command "{}" returned no output'.format('GET_FW_VERSION'))
            return
        if len(self.health_data) == 0:
            log.warning('Command "{}" returned no output'.format('GET_EMBEDDED_HEALTH_DATA'))
            return

        maps.append(self.get_device_map())
        maps.append(self.get_chassis_maps())
        maps.append(self.get_sys_board())
        maps.append(self.get_mgmt_ctrl())
        maps.append(self.get_processors())
        maps.append(self.get_memory(log))
        maps.append(self.get_fans(log))
        maps.append(self.get_temp_sensors(log))
        maps.append(self.get_power_supplies(log))
        maps.extend(self.get_storage_maps(log))
        maps.append(self.get_nics(log))

        log.info('Maps:{}'.format(maps))

        # TODO: Send clear event when modeling is OK
        # dedupid: 	alcohol-ilo.in.credoc.be||/Status/Update|4|Problem while executing plugin ilo2.HPILO2Modeler
        # component: null
        # eventClass: /Status/Update
        return maps

    # Global info
    def get_product_serial(self):
        self.product = self.find_host_data_item('Product Name')
        self.serial = self.find_host_data_item('Serial Number').strip()
        self.product_id = self.product.replace(self.serial, '')

    def get_ilo_info(self):
        """find out some global ILO info"""
        for item in self.get_health_data_section('NIC_INFORMATION'):
            data = self.parser.get_merged(item.get('NIC', []))
            # this is probably the ILO
            if len(data) == 0:
                try:
                    key = item.keys()[0]
                except:
                    continue
                data = self.parser.get_merged(item.get(key, []))
            # we'll pull out some global info from this then
            if len(data) > 0:
                ipaddr = data.get('IP_ADDRESS', {}).get('VALUE')
                if ipaddr != 'N/A':
                    self.ilo_ipaddr = ipaddr

    def get_chassis_mem(self, log):
        record = self.get_host_data_records('Memory Device')
        for item in record:
            memorySize = self.get_field_value(item, 'Size')
            if not memorySize.lower() == 'not installed':
                self.total_mem += self.standardize(memorySize)
        return

    # Parser helpers
    def get_health_data_section(self, key):
        """return component object data from a given section"""
        for h in self.health_data:
            if key in h.keys():
                return h.get(key, [])
        return []

    def find_host_data_item(self, key, tagk='NAME', tagv='VALUE'):
        for item in self.host_data:
            # print('host_data_item: {}'.format(item))
            record = item.get('SMBIOS_RECORD', [])
            for i in record:
                field = i.get('FIELD')
                if field.get(tagk) == key:
                    return field.get(tagv)
        return 'Unknown'

    def get_host_data_records(self, key):
        result = []
        for item in self.host_data:
            record = item.get('SMBIOS_RECORD', [])
            for i in record:
                field = i.get('FIELD')
                if field.get('NAME') == 'Subject' and field.get('VALUE') == key:
                    result.append(record)
        return result

    def get_field_value(self, fields, name):
        for field in fields:
            if field['FIELD']['NAME'] == name:
                return field['FIELD']['VALUE']
        return

    # Components modelers
    def get_device_map(self):
        '''Device Map'''
        om = self.objectMap()
        om.setHWProductKey = MultiArgs(self.product, 'HPILO2')
        om.setHWSerialNumber = self.serial
        om.snmpSysName = self.server_name
        om.snmpDescr = self.product_id
        return om

    def get_chassis_maps(self):
        """HPILO2Chassis"""
        ob_map = get_object_map('HPILO2Chassis')
        om = ObjectMap(ob_map)
        name = self.serial
        om.id = prepId(name)
        om.title = name
        om.serverName = self.server_name
        om.serialNo = self.serial
        om.productId = self.product_id
        om.productName = self.product
        om.totalRam = self.total_mem
        # TODO: error on following
        om.perfId = "HPILO2Chassis"
        self.compname = 'hpilo2chassis/%s' % om.id
        # TODO: enhance relationship name
        return RelationshipMap(relname='hpilo2chassis',
                               modname='ZenPacks.community.HPILO2.HPILO2Chassis',
                               objmaps=[om])

    def get_sys_board(self):
        """HPILO2SystemBoard"""
        ob_map = get_object_map('HPILO2SystemBoard')
        om = ObjectMap(ob_map)
        name = self.product
        om.id = prepId(name)
        om.title = name
        om.romVer = '{} {}'.format(self.find_host_data_item('Family'),
                                   self.find_host_data_item('Date'))
        om.serialNo = self.serial
        om.productName = self.product
        return RelationshipMap(relname='hpilo2systemboard',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2SystemBoard',
                               objmaps=[om])

    def get_mgmt_ctrl(self):
        """Management Controller"""
        ob_map = get_object_map('HPILO2ManagementController')
        om = ObjectMap(ob_map)
        name = self.fw_data.get('MANAGEMENT_PROCESSOR', 'Unknown')
        om.id = prepId(name)
        om.title = name
        om.firmware = self.fw_data.get('FIRMWARE_VERSION', 'Unknown')
        om.firmwareDate = self.fw_data.get('FIRMWARE_DATE', 'Unknown')
        om.licenseType = self.fw_data.get('LICENSE_TYPE', 'Unknown')
        om.ipv4Address = self.ilo_ipaddr
        om.perfId = "HPManagementController"
        return RelationshipMap(relname='hpilo2managementcontroller',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2ManagementController',
                               objmaps=[om])

    def get_processors(self):
        """HPProcessor"""
        maps = []
        for item in self.get_host_data_records('Processor Information'):
            '''Processor item [{'FIELD': {'NAME': 'Subject', 'VALUE': 'Processor Information'}},
                {'FIELD': {'NAME': 'Label', 'VALUE': 'Proc 1'}}, 
                {'FIELD': {'NAME': 'Speed', 'VALUE': '2400 MHz'}}, 
                {'FIELD': {'NAME': 'Execution Technology', 'VALUE': '4 of 4 cores; 8 threads'}}, 
                {'FIELD': {'NAME': 'Memory Technology', 'VALUE': '64-bit extensions'}}, 
                {'FIELD': {'NAME': 'Family', 'VALUE': '179'}}]
            '''
            ob_map = get_object_map('HPILO2Processor')
            om = ObjectMap(ob_map)
            name = self.get_field_value(item, 'Label')
            if not name or name == '':
                continue
            om.id = prepId(name)
            # model = data.get('NAME', {}).get('VALUE', '')
            # om.title = model.replace('(R)', '').split('@')[0].strip()
            # TODO: following is creating error (perfId)
            om.perfId = name
            # om.model = model
            # TODO: Add speed to CPU
            # TODO: Add hyperthread to CPU
            # TODO: Add model to CPU
            om.speed = self.standardize(self.get_field_value(item, 'Speed'))
            tech = self.get_field_value(item, 'Execution Technology')
            try:
                om.coreCount = re.findall(r'(\d)/\d cores', tech)[0]
            except:
                pass
            try:
                om.threadCount = re.findall(r'(\d) threads', tech)[0]
            except:
                pass
            maps.append(om)
        return RelationshipMap(relname='hpilo2processors',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2Processor',
                               objmaps=maps)

    def get_memory(self, log):
        """HPProcessor"""
        maps = []
        for item in self.get_host_data_records('Memory Device'):
            # log.debug('MEM item:{}'.format(item))
            ob_map = get_object_map('HPILO2Memory')
            om = ObjectMap(ob_map)
            name = self.get_field_value(item, 'Label')
            if not name or name == '':
                continue
            om.id = prepId(name)
            om.perfId = name
            size = self.get_field_value(item, 'Size')
            if not size or size == 'not installed':
                continue
            om.size = self.standardize(size)
            om.speed = self.standardize((self.get_field_value(item, 'Speed')))
            maps.append(om)
        return RelationshipMap(relname='hpilo2memories',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2Memory',
                               objmaps=maps)

    def get_fans(self, log):
        maps = []
        for item in self.get_health_data_section('FANS'):
            # log.debug('Fan: {}'.format(item))
            data = self.parser.get_merged(item.get('FAN', []))
            ob_map = get_object_map('HPILO2CoolingFan')
            om = ObjectMap(ob_map)
            name = data.get('LABEL', {}).get('VALUE')
            if not name:
                continue
            om.id = prepId(name)
            om.title = name
            om.zone = data.get('ZONE', {}).get('VALUE')
            maps.append(om)
        return RelationshipMap(relname='hpilo2coolingfans',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2CoolingFan',
                               objmaps=maps)

    def get_temp_sensors(self, log):
        maps = []
        for item in self.get_health_data_section('TEMPERATURE'):
            # log.debug('Temperature: {}'.format(item))
            data = self.parser.get_merged(item.get('TEMP', []))
            ob_map = get_object_map('HPILO2Temperature')
            om = ObjectMap(ob_map)
            name = data.get('LABEL', {}).get('VALUE')
            if not name:
                continue
            om.id = prepId(name)
            om.title = name
            om.location = data.get('LOCATION', {}).get('VALUE')
            om.caution = data.get('CAUTION', {}).get('VALUE')
            om.critical = data.get('CRITICAL', {}).get('VALUE')
            maps.append(om)
        return RelationshipMap(relname='hpilo2temperatures',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2Temperature',
                               objmaps=maps)

    def get_power_supplies(self, log):
        maps = []
        for item in self.get_health_data_section('POWER_SUPPLIES'):
            # log.debug('Power supply: {}'.format(item))
            data = self.parser.get_merged(item.get('SUPPLY', []))
            ob_map = get_object_map('HPILO2PowerSupply')
            om = ObjectMap(ob_map)
            name = data.get('LABEL', {}).get('VALUE')
            if not name:
                continue
            om.id = prepId(name)
            om.title = name
            maps.append(om)
        return RelationshipMap(relname='hpilo2powersupplies',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2PowerSupply',
                               objmaps=maps)

    def get_storage_maps(self, log):
        maps = []
        drive_mappings = {
            'DRIVE': ('bayIndex', 'BAY'),
            'PRODUCT': ('productId', 'ID'),
            'DRIVE_STATUS': ('driveStatus', 'VALUE'),
        }
        for backplane in self.get_health_data_section('DRIVES'):
            # log.debug('Drives: {}'.format(backplane))
            backplane = backplane.get('BACKPLANE', [])
            ob_map = get_object_map('HPILO2PhysicalDrive')
            om = ObjectMap(ob_map)

            '''2017-11-06 14:14:16,853 INFO zen.ZenModeler: Drives: 
                {'BACKPLANE': [{'FIRMWARE': {'VERSION': '1.16'}}, {'ENCLOSURE': {'ADDR': '224'}}, 
                        {'DRIVE': {'BAY': '1'}}, {'PRODUCT': {'ID': 'GJ0250EAGSQ    '}}, {'DRIVE_STATUS': {'VALUE': 'Ok'}}, {'UID': {'LED': 'Off'}}, 
                        {'DRIVE': {'BAY': '2'}}, {'PRODUCT': {'ID': 'GJ0250EAGSQ    '}}, {'DRIVE_STATUS': {'VALUE': 'Ok'}}, {'UID': {'LED': 'Off'}}, 
                        {'DRIVE': {'BAY': '3'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}, 
                        {'DRIVE': {'BAY': '4'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}
                        ]}
            '''

            for data in backplane:
                log.debug('storage data: {}'.format(data))
                key = data.keys()[0]
                log.debug('storage key: {}'.format(key))
                if key in drive_mappings.keys():
                    attr_name, tag = drive_mappings[key]
                    setattr(om, attr_name, data[key].get(tag, ''))
                if key == 'UID': # take into account 'not installed'
                    om.productId = om.productId.strip()
                    om.id = prepId('BAY {}'.format(om.bayIndex))
                    om.title = 'BAY {}'.format(om.bayIndex)
                    maps.append(om)
                    om = ObjectMap(ob_map)


            ''' 
            [{'FIRMWARE': {'VERSION': '1.16'}}, 
                {'ENCLOSURE': {'ADDR': '226'}}, 
                {'DRIVE': {'BAY': '5'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}, 
                {'DRIVE': {'BAY': '6'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}, 
                {'DRIVE': {'BAY': '7'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}, 
                {'DRIVE': {'BAY': '8'}}, {'PRODUCT': {'ID': 'N/A'}}, {'DRIVE_STATUS': {'VALUE': 'Not Installed'}}, {'UID': {'LED': 'Off'}}]
            '''

        return RelationshipMap(relname='hpilo2physicaldrives',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2PhysicalDrive',
                               objmaps=maps)

    def get_nics(self, log):
        maps = []
        return RelationshipMap(relname='hpilo2networkinterface',
                               compname=self.compname,
                               modname='ZenPacks.community.HPILO2.HPILO2NetworkInterface',
                               objmaps=maps)

    # - HPILO2Chassis(hpilo2pcidevices)    1:MC    HPILO2PCIDevice

    # Formatters
    def standardize(self, value):
        speed, units = value.split(' ')
        speed = int(speed)
        units = units.lower()
        if units.startswith('k'):
            return speed
        if units.startswith('m'):
            return speed * 1024 ** 2
        if units.startswith('g'):
            return speed * 1024 ** 3
        if units.startswith('t'):
            return speed * 1024 ** 4
        return 0



