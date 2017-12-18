#
# coding: utf-8

from twisted.internet.defer import DeferredSemaphore, DeferredList, inlineCallbacks, returnValue, deferredGenerator
from twisted.web.client import getPage

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenUtils.Utils import prepId

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.community.HPILO2.lib.ILO2ProtocolHandler import ILO2ProtocolHandler
from ZenPacks.community.HPILO2.lib.ILO2XMLParser import parse, get_merged, get_health_data_section

import logging
log = logging.getLogger('zen.HPILO2')


class HPILO2DataSourcePlugin(PythonDataSourcePlugin):
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
        log.info(
            'In config_key context.device().id is %s datasource.getCycleTime(context) is %s \ '
            'datasource.plugin_classname is %s  ' % (
                context.device().id, datasource.getCycleTime(context), datasource.plugin_classname))
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname,
        )

    @classmethod
    def params(cls, datasource, context):
        log.debug('Starting HPChassis params')
        params = {}
        log.debug('params is {} \n'.format(params))
        return params

    @classmethod
    def get_cmd(cls, cmd='GET_EMBEDDED_HEALTH', tag='SERVER_INFO'):
        """return formatted RIBCL command"""
        return '<{} MODE=\"read\"><{}/></{}>'.format(tag, cmd, tag)

    @inlineCallbacks
    def collect(self, config):
        ds0 = config.datasources[0]
        ip_address = config.manageIp
        client = ILO2ProtocolHandler(ip_address,
                                     ds0.zILO2Port,
                                     ds0.zILO2UserName,
                                     ds0.zILO2Password,
                                     ds0.zILO2UseSSL,
                                     ds0.zCollectorClientTimeout)
        data = yield client.send_command(self.get_cmd('GET_EMBEDDED_HEALTH'))
        log.debug('collect data is %s ' % data)
        returnValue(data)

    def onResult(self, result, config):
        # log.debug('result is %s ' % result)
        return result

    def get_fans_data(self, config, comp_data, component):
        status_maps = {
            'OK': 0,            # Clear
            'DEGRADED': 3,      # Warning
            'FAILED': 5,        # Critical
        }
        ds0 = config.datasources[0]

        data = self.new_data()
        for item in comp_data:
            item_data = get_merged(item.get('FAN', []))
            if component == item_data.get('LABEL', {}).get('VALUE'):
                speed = item_data.get('SPEED', {}).get('VALUE')
                status = item_data.get('STATUS', {}).get('VALUE')
                status_value = status_maps.get(status.upper(), 3)
                comp_data.remove(item)
                break
        data['values'][prepId(component)]['statusfan'] = (status_value, 'N')
        data['values'][prepId(component)]['speed'] = (speed, 'N')
        data['events'].append({
            'device': config.id,
            'component': component,
            'severity': status_value,
            'eventKey': ds0.plugin_classname,
            'eventClassKey': 'FanStatus',
            'summary': 'Fan status is {}'.format(status),
            'eventClass': '/HW/Temperature/Fan',
        })
        return data

    def get_temps_data(self, config, comp_data, component):
        status_maps = {
            'OK': 0,                # Clear
            'DEGRADED': 3,          # Warning
            'FAILED': 5,            # Critical
            'NOT INSTALLED': 0,     # Clear
            'N/A': 0,               # Clear
        }
        ds0 = config.datasources[0]
        data = self.new_data()
        for item in comp_data:
            item_data = get_merged(item.get('TEMP', []))
            if component == item_data.get('LABEL', {}).get('VALUE'):
                reading = float(item_data.get('CURRENTREADING', {}).get('VALUE'))
                caution = float(item_data.get('CAUTION', {}).get('VALUE'))
                critical = float(item_data.get('CRITICAL', {}).get('VALUE'))
                status = item_data.get('STATUS', {}).get('VALUE')
                status_value = status_maps.get(status.upper(), 3)
                comp_data.remove(item)
                break
        data['values'][prepId(component)]['statustemp'] = (status_value, 'N')
        data['values'][prepId(component)]['temperature_reading'] = (reading, 'N')
        if reading >= critical:
            data['events'].append({
                'device': config.id,
                'component': component,
                'severity': 5,
                'eventKey': ds0.plugin_classname,
                'eventClassKey': 'TemperatureReading',
                'summary': 'Temperature is critical, reading {} °C'.format(reading),
                'eventClass': '/HW/Temperature',
            })
        elif reading >= caution:
            data['events'].append({
                'device': config.id,
                'component': component,
                'severity': 3,
                'eventKey': ds0.plugin_classname,
                'eventClassKey': 'TemperatureReading',
                'summary': 'Temperature is in warning, reading {} °C'.format(reading),
                'eventClass': '/HW/Temperature',
            })
        else:
            data['events'].append({
                'device': config.id,
                'component': component,
                'severity': 0,
                'eventKey': ds0.plugin_classname,
                'eventClassKey': 'TemperatureReading',
                'summary': 'Temperature is OK, reading {} °C'.format(reading),
                'eventClass': '/HW/Temperature',
            })
        data['events'].append({
            'device': config.id,
            'component': component,
            'severity': status_value,
            'eventKey': ds0.plugin_classname,
            'eventClassKey': 'TemperatureStatus',
            'summary': 'Temperature status is {}'.format(status),
            'eventClass': '/HW/Temperature',
        })
        return data

    def get_powersupplies_data(self, config, comp_data, component):
        status_maps = {
            'OK': 0,                    # Clear
            'DEGRADED': 3,              # Warning
            'FAILED': 5,                # Critical
            'NOT INSTALLED': 0,         # Clear
            'GOOD, IN USE': 0,          # Clear
            'INPUT VOLTAGE LOST': 3,    # Warning
        }
        ds0 = config.datasources[0]
        data = self.new_data()
        for item in comp_data:
            item_data = get_merged(item.get('SUPPLY', []))
            if component == item_data.get('LABEL', {}).get('VALUE'):
                status = item_data.get('STATUS', {}).get('VALUE')
                status_value = status_maps.get(status.upper(), 3)
                comp_data.remove(item)
                break
        data['values'][prepId(component)]['statusps'] = (status_value, 'N')
        data['events'].append({
            'device': config.id,
            'component': component,
            'severity': status_value,
            'eventKey': ds0.plugin_classname,
            'eventClassKey': 'PowerSupplyStatus',
            'summary': 'Power Supply status is {}'.format(status),
            'eventClass': '/HW/Power',
        })
        return data

    def get_drives_data(self, config, comp_data, component):
        status_maps = {
            'OK': 0,                            # Clear
            'FAILED': 5,                        # Critical
            'PREDICTIVE FAILURE': 3,            # Warning
            'ERASING': 3,                       # Warning
            'ERASE DONE': 3,                    # Warning
            'ERASE QUEUED': 3,                  # Warning
            'SSD WEAR OUT': 3,                  # Warning
            'NOT AUTHENTICATED': 3,             # Warning
            'NOT INSTALLED': 0,                 # Clear
            'NOT PRESENT/NOT INSTALLED': 0,     # Clear
        }
        ds0 = config.datasources[0]
        data = self.new_data()
        found_bay = False
        for backplane in comp_data:
            backplane_data = backplane.get('BACKPLANE')
            for item in backplane_data:
                if item.keys()[0] == 'DRIVE' and 'Bay {}'.format(item['DRIVE']['BAY']) == component:
                    found_bay = True
                if found_bay and item.keys()[0] == 'DRIVE_STATUS':
                    status = item.get('DRIVE_STATUS').get('VALUE')
                    status_value = status_maps.get(status.upper(), 3)
                    break
            if status:
                break
        data['values'][prepId(component)]['statuspdrive'] = (status_value, 'N')
        data['events'].append({
            'device': config.id,
            'component': component,
            'severity': status_value,
            'eventKey': ds0.plugin_classname,
            'eventClassKey': 'PhysicalDriveStatus',
            'summary': 'Physical Drive status is {}'.format(status),
            'eventClass': '/HW/Store',
        })
        return data

    def onSuccess(self, result, config):
        maps = {
            'fan': {'tag': 'FANS', 'func': 'get_fans_data'},
            'temperature': {'tag': 'TEMPERATURE', 'func': 'get_temps_data'},
            'powersupply': {'tag': 'POWER_SUPPLIES', 'func': 'get_powersupplies_data'},
            'physicaldrive': {'tag': 'DRIVES', 'func': 'get_drives_data'},
        }
        data = self.new_data()
        parsed = parse(result)
        health_comp_data = None
        health_data = parsed.get('GET_EMBEDDED_HEALTH_DATA', {})
        ds0 = config.datasources[0]
        if ds0.datasource in maps.keys():
            tag = maps[ds0.datasource]['tag']
            get_comp_data = getattr(self, maps[ds0.datasource]['func'])
            health_comp_data = get_health_data_section(health_data, tag)

        for ds in config.datasources:
            if health_comp_data:
                comp_data = get_comp_data(config, health_comp_data, ds.component)
                for k, v in comp_data.items():
                    if k in ['maps', 'events']:
                        data[k].extend(v)
                    else:
                        data[k].update(v)
        log.debug('HPILO2DataSourcePlugin data: {}'.format(data))
        return data

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
                'summary': 'Error getting HPILO2DataSourcePlugin component data with zenpython: %s' % result,
                'eventKey': 'HPILO2DataSourcePlugin',
                'severity': 4,
            }],
        }

    def onComplete(self, result, config):
        """
        Called last for success and error.

        You can omit this method if you want the result of either the
        onSuccess or onError method to be used without further processing.
        """
        log.debug('Starting HPILO2DataSourcePlugin onComplete')
        return result


class HPILO2DataSourcePluginPower(PythonDataSourcePlugin):
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
            'In config_key context.device().id is %s datasource.getCycleTime(context) is %s \
            datasource.rrdTemplate().id is %s datasource.id is %s datasource.plugin_classname is %s  ' % (
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
        ip_address = config.manageIp
        client = ILO2ProtocolHandler(ip_address,
                                     ds0.zILO2Port,
                                     ds0.zILO2UserName,
                                     ds0.zILO2Password,
                                     ds0.zILO2UseSSL,
                                     ds0.zCollectorClientTimeout)
        data = yield client.send_command(self.get_cmd('GET_POWER_READINGS'))
        returnValue(data)

    def onResult(self, result, config):
        # log.debug('result is %s ' % result)
        return result

    def onSuccess(self, result, config):
        ds0 = config.datasources[0]
        component = ds0.component
        data = self.new_data()
        parsed = parse(result)
        power_readings = parsed.get('GET_POWER_READINGS', [])
        for item in power_readings:
            present = item.get('PRESENT_POWER_READING', '')
            if present:
                value = float(present['VALUE'])
                data['values'][component]['power_reading'] = (value, 'N')
                break
        log.debug('HPILO2DataSourcePluginPower data: {}'.format(data))
        return data

