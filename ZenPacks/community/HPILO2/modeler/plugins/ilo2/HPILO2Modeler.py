
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
        log.info('Results:{}'.format(results))

        #self.ilo_ipaddr = None
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
        maps = []
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
        om.perfId = "HPILO2Chassis"
        self.compname = 'hpilo2chassis/%s' % om.id
        maps.append(om)
        return RelationshipMap(relname='hpilo2chassis',
                               modname='ZenPacks.community.HPILO2.HPILO2Chassis',
                               objmaps=maps)


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



