##############################################################################
#
# Copyright (C) Zenoss, Inc. 2012, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
import os
import collections
from lxml import etree
import logging
log = logging.getLogger('zen.ILO2XMLParser')


# TODO: there should be no need to use a class, a module library with functions should be OK
# class ILO2XMLParser(object):
#     '''Parser for ILO2 XML output'''

def find_item(target, tag, label, items):
    ''' return dictionary based on tag given a
        list of dictionaries
    '''
    if not isinstance(items, list):
        log.warn('find_item only accepts list: {}'.format(items))
        return
    items = self.get_merged_items(items)
    for i in items:
        if i.get(tag, {}).get(label) == target:
            log.debug('Match ({}) found for target ({}) using {}:{}'.format(i, target, tag, label))
            return i
    return

def get_merged_items(items):
    '''return list of dictionaries'''
    output = []
    if not isinstance(items, list):
        log.warn('get_merged_items only accepts list: {}'.format(items))
        return output
    for i in items:
        if not isinstance(i, dict):
            log.warn('get_merged_items cannot parse non-dict item: {}'.format(i))
            continue
        vals = i.values()
        if len(vals) == 0:
            log.warn('get_merged_items found empty dict: {}'.format(i))
            continue
        if len(vals) > 1:
            log.warn('get_merged_items found multiple entries for: {}'.format(i))
            continue
        try:
            merged = self.get_merged(vals[0])
            output.append(merged)
        except Exception as e:
            log.warn('Error ({}) occurred while parsing {} ({})'.format(e, i, vals))
    return output

def get_merged(items):
    '''return recursively merged dictionary'''
    def merge_dict(target, source):
        for k, v in source.items():
            if (k in target and isinstance(target[k], dict)
                    and isinstance(source[k], collections.Mapping)):
                merge_dict(target[k], source[k])
            else:
                target[k] = source[k]
    new = {}
    for i in items:
        merge_dict(new, i)
    return new

def get_items_by_key(key, items):
    '''return items with a given key'''
    output = []
    for i in items:
        if key in i.keys():
            output.append(i)
    return output

def normalize(results):
    new = {}
    for r in results:
        ribcl = r.get('RIBCL')
        for k in ribcl:
            new.update(k)
    return new

def to_skip(ele):
    '''don't bother processing this element'''
    keys = ele.attrib.keys()
    if len(keys) == 0:
        return True
    keys.sort()
    if len(keys) == 2 and keys == ['B64_DATA', 'TYPE']:
        return True
    return False


def parse(xml_doc):
    results = []
    root = load_xml_doc(xml_doc)
    if root is None:
        return results
    if isinstance(root, etree._Element) or isinstance(root, etree._ElementTree):
        for r in root.findall('RIBCL'):
            stat = get_response_status(r)
            version = stat.get('VERSION', 'Unknown')
            message = stat.get('MESSAGE', 'Unknown')
            code = stat.get('STATUS', 'Unknown')
            info = self.get_info(r)
            # log any failure messages
            if stat.get('MESSAGE', 'Unknown') != 'No error':
                msg = 'RIBCL (V: {}) returned: {} ({})'.format(version, message, code)
                log.warning(msg)
            results.append(info)
    else:
        log.error('Error parsing XML document')
    log.info('parse results: {}'.format(results))
    return self.normalize(results)

def find_items_by_tag(data, tag):
    '''recursive search for data dictionaries with a given key'''
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == tag:
                items.append({k: v})
            if isinstance(v, list):
                for u in v:
                    items += self.find_items_by_tag(u, tag)
    elif isinstance(data, list):
        for d in data:
            items += self.find_items_by_tag(d, tag)
    return items

def get_info(element, skipped=None):
    '''return combo list/dictionary representing element
    '''
    info = []
    for x in element.iterchildren('*'):
        if self.to_skip(x):
            ob = self.get_info(x, x.attrib)
        else:
            ob = {x.tag: dict(x.attrib)}
        if isinstance(ob.get(x.tag), list) and len(ob.get(x.tag)) == 0:
            continue
        info.append(ob)
    if skipped:
        info.append(skipped)
    return {element.tag: info}

def get_useful_data(parsed):
    '''return True if parsed data is useful'''
    output = parsed.get('RIBCL', {}).copy()
    skip_keys = ['items', 'VERSION', 'RESPONSE', 'INFORM']
    parsed_keys = output.keys()
    useful_keys = [k for k in parsed_keys if k not in skip_keys]
    for k in output.keys():
        if k not in useful_keys:
            output.pop(k)
    return output


def load_xml_doc(xml_doc):
    '''return etree from file or string'''
    if not xml_doc:
        return None
    result = None
    if os.path.isfile(xml_doc):
        try:
            result = etree.parse(xml_doc)
        except Exception as e:
            log.error('Error loading XML document ({})'.format(e))
    else:
        try:
            result = etree.fromstring(xml_doc)
        except Exception as e:
            log.error('Error loading XML document ({})'.format(e))
    return result

def get_response_status(element):
    '''determine query response code'''
    data = {}
    if isinstance(element, etree._Element) or isinstance(element, etree._ElementTree):
        data.update(dict(element.attrib))
        response = element.find('RESPONSE')
        if response is not None:
            data.update(dict(response.attrib))
    return data
