##############################################################################
#
# Copyright (C) Zenoss, Inc. 2012, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
from twisted.internet.defer import DeferredSemaphore, DeferredList, inlineCallbacks, returnValue

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin

from ZenPacks.community.HPILO2.lib.ILO2XMLParser import ILO2XMLParser
from ZenPacks.community.HPILO2.lib.ILO2ProtocolHandler import ILO2ProtocolHandler
from .HPPluginBase import HPPluginBase

def get_cmd(cmd='GET_EMBEDDED_HEALTH', tag='SERVER_INFO'):
    '''return formatted RIBCL command'''
    return '<{} MODE=\"read\"><{}/></{}>'.format(tag, cmd, tag)

class ilo2Plugin(HPPluginBase, PythonPlugin):
    '''iloPlugin'''
    deviceProperties = HPPluginBase.deviceProperties + \
        PythonPlugin.deviceProperties + \
        ('zILO2UserName', 'zILO2Password', 'zILO2UseSSL', 'zILO2Port', 'zCollectorClientTimeout')
    serverDetails = None
    # version = 3
    parser = ILO2XMLParser()

    @inlineCallbacks
    def collect(self, device, log):
        log.info('*** ilo2Plugin Collecting for {}'.format(device.id))

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

