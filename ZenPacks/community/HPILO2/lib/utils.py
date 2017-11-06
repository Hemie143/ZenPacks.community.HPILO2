
from cStringIO import StringIO
from lxml import etree

import logging
LOG = logging.getLogger('ZenPacks.community.HPILO2.utils')


def iterparse(xml, tag):
    '''
    Generate elements with a tag in xml string.
    '''
    for action, element in etree.iterparse(StringIO(xml), tag=tag):
        yield element
        element.clear()

def build_single_tag_multi_entry(element, mappings):
    '''
    Return ObjectMap instance given etree element and mappings.
    '''
    om = ObjectMap()
    el = element
    # testElement(el)
    i = 0
    for attr_name, expr, transform, attribute, valueType in mappings:
        i = i + 1
        transform_args = []
        subElememt = el.find(expr)
        if subElememt is not None:
            transform_args.append(subElememt.get(attribute))
            attributeValue = subElememt.get(attribute)
            xpathValue = ".//%s[@%s='%s']" % (expr, attribute, attributeValue)
            oldTag = el.xpath(xpathValue)
            oldTag[0].getparent().remove(oldTag[0])
        else:
            transform_args.append(None)
        try:
            setattr(om, attr_name, transform(*transform_args))
        except Exception:
            pass

    return tuple((om, el))