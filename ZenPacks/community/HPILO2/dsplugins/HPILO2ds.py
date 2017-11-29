#
from twisted.internet.defer import DeferredSemaphore, DeferredList, inlineCallbacks, returnValue, deferredGenerator
from twisted.web.client import getPage

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.community.HPILO2.lib.ILO2ProtocolHandler import ILO2ProtocolHandler

import logging
log = logging.getLogger('zen.HPILO2')


# TODO: Move this function to a better place
def get_cmd(cmd='GET_EMBEDDED_HEALTH', tag='SERVER_INFO'):
    """return formatted RIBCL command"""
    return '<{} MODE=\"read\"><{}/></{}>'.format(tag, cmd, tag)


class HPChassis(PythonDataSourcePlugin):
    # List of device attributes you might need to do collection.

    proxy_attributes = (
        'zILO2UserName',
        'zILO2Password',
        'zILO2UseSSL',
        'zILO2Port',
        'zCollectorClientTimeout',
        )

    @classmethod
    def config_key(cls, datasource, context):
        log.debug(
            'In config_key context.device().id is %s datasource.getCycleTime(context) is %s datasource.rrdTemplate().id is %s datasource.id is %s datasource.plugin_classname is %s  ' % (
            context.device().id, datasource.getCycleTime(context), datasource.rrdTemplate().id, datasource.id,
            datasource.plugin_classname))
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.rrdTemplate().id,
            datasource.id,
            datasource.plugin_classname,
        )

    @classmethod
    def params(cls, datasource, context):
        log.debug('Starting HPChassis params')
        params = {}
        log.debug('params is {} \n'.format(params))
        return params

    @inlineCallbacks
    def collect(self, config):
        ds0 = config.datasources[0]
        log.info('config: {}'.format(ds0))
        log.info('zILO2Port: {}'.format(config.datasources[0].zILO2Port))

        ip_address = config.manageIp
        log.info('ip_address: {}'.format(ip_address))


        client = ILO2ProtocolHandler(ip_address,
                                     ds0.zILO2Port,
                                     ds0.zILO2UserName,
                                     ds0.zILO2Password,
                                     ds0.zILO2UseSSL,
                                     ds0.zCollectorClientTimeout)

        # log.info('client: {}'.format(client))
        # d = client.send_command(get_cmd('GET_EMBEDDED_HEALTH'))

        data = self.new_data()

        # TODO : loop in datasources ?
        # TODO : yield result
        '''
        deferreds = []
        sem = DeferredSemaphore(1)
        for datasource in config.datasources:
            log.info('datasource: {}'.format(datasource.datasource))
            d = sem.run(client.send_command, get_cmd('GET_EMBEDDED_HEALTH'))
            # results = yield DeferredList(deferreds, consumeErrors=True)
            deferreds.append(d)
        '''
        sem = DeferredSemaphore(1)
        # d = sem.run(client.send_command, get_cmd('GET_EMBEDDED_HEALTH'))
        data = yield client.send_command(get_cmd('GET_EMBEDDED_HEALTH'))
        # returnValue(data)
        # return DeferredList(deferreds)
        #return d
        returnValue(data)

    def onResult(self, result, config):
        """
        Called first for success and error.

        You can omit this method if you want the result of the collect method
        to be used without further processing.
        """
        log.debug('result is %s ' % (result))

        return result

    def onSuccess(self, result, config):
        return result

    def onError(self, result, config):
        """
        Called only on error. After onResult, before onComplete.

        You can omit this method if you want the error result of the collect
        method to be used without further processing. It recommended to
        implement this method to capture errors.
        """
        log.debug('In OnError - result is %s and config is %s ' % (result, config))
        return {
            'events': [{
                'summary': 'Error getting Snmp component services data with zenpython: %s' % result,
                'eventKey': 'PythonSnmpWinServComponent',
                'severity': 4,
            }],
        }

    def onComplete(self, result, config):
        """
        Called last for success and error.

        You can omit this method if you want the result of either the
        onSuccess or onError method to be used without further processing.
        """
        log.debug('Starting SnmpRaritanTempSensor onComplete')
        return result

