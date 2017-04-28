
# stdlib imports
# Twisted imports

# Zenoss imports
#from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from ZenPacks.community.HPILO2.modeler.ilo2Plugin import ilo2Plugin, get_cmd

class HPILO2Modeler(ilo2Plugin):

    serverDetails = [
        get_cmd('GET_SERVER_NAME'),
        get_cmd('GET_EMBEDDED_HEALTH'),
        get_cmd('GET_HOST_DATA'),
        get_cmd('GET_FW_VERSION', tag='RIB_INFO'),
        ]

    def process(self, device, results, log):
        log.info('Processing {} for device {}'.format(self.name(), device.id))
        log.info('Results:{}'.format(results))

        maps = []

