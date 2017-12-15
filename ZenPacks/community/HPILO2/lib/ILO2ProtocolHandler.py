#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016 all rights reserved.
#
# You should have received a copy of the GNU General Public License
# along with this ZenPack. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import time

from twisted.internet import ssl, reactor
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet.error import TimeoutError
from twisted.internet.defer import CancelledError

from zope.interface import implements

import logging
logging.basicConfig()
log = logging.getLogger('zen.ILO2ProtocolHandler')


class Ilo2ClientException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Ilo2RawProtocol(Protocol):

    def __init__(self):
        self.finished = Deferred()
        self._data = None

    def sendMessage(self, msg):
        self.transport.write(msg)
        return self.finished

    def dataReceived(self, data):
        if (self._data is None):
            self._data = data
        else:
            self._data = self._data+data

    def connectionLost(self, reason):
        if reason.getErrorMessage() == 'Connection was closed cleanly.':
            if 'Login credentials rejected.' in self._data:
                self.finished.cancel()
                log.warn('Wrong username/password')
            else:
                self.finished.callback(self._data)
        else:
            self.finished.cancel()
            log.warn('Connection Lost - Connection closed non-clean manner.')


class Ilo2Factory(Factory):
    protocol = Ilo2RawProtocol


class ILO2ProtocolHandler(object):
    '''ILO2 Client'''

    def __init__(self, host, port, username, password, ssl=False, timeout=60, ribcl='2.22'):
        self.host = host
        self.port = int(port)
        self.ssl = ssl
        self.username = username
        self.password = password
        self.ribcl = ribcl
        self.timeout = timeout
        self._factory = Ilo2Factory()

    @inlineCallbacks
    def send_command(self, cmd):
        self._duration = '5'
        xml_request = self.format_request(cmd)
        self._msg = xml_request
        log.debug('Sending XML: {}'.format(xml_request))
        endpoint = yield self.connect()
        df = yield self.writeProtocol(endpoint, self._msg)
        response = str(df)
        #return self.get(xml_request)
        returnValue(self.xml_cleanup(response))

    def writeProtocol(self, p, data):
        p.sendMessage(data)
        return p.finished

    def test_request(self):
        ''''example request'''
        #return self.send_command(self.get_cmd('GET_SERVER_NAME'))
        return self.send_command(self.get_cmd('GET_SERVER_NAME'))

    def format_request(self, body):
        '''boilerplate xml body'''
        envelope = '<?xml version=\"1.0\"?>' \
                   '<RIBCL VERSION="{}">' \
                    '<LOGIN USER_LOGIN="{}" PASSWORD="{}">' \
                    '{}</LOGIN></RIBCL>\r\n'
        return envelope.format(self.ribcl, self.username, self.password, body)

    def get_cmd(self, cmd='GET_EMBEDDED_HEALTH', tag='SERVER_INFO'):
        '''return formatted RIBCL command'''
        return '<{} MODE=\"read\"><{}/></{}>'.format(tag, cmd, tag)

    @inlineCallbacks
    def connect(self):
        endpoint = yield SSL4ClientEndpoint(
                        reactor,
                        self.host,
                        self.port,
                        ssl.ClientContextFactory()).connect(self._factory)
        returnValue(endpoint)

    def _req(self, data=None):
        """return Deferred request the ILO """
        log.debug('Sending to {}:\n{}'.format(self.host, data))
        endpoint = yield self.connect()
        df = yield self.writeProtocol(endpoint, data)
        response = str(df)
        returnValue(response)

    @inlineCallbacks
    def _request(self, data=None):
        """Asynchronously request the XML query.
        """
        result = None
        try:
            result = yield self._req(data)
        except TimeoutError as e:
            log.error('Timeout connecting to {} ()'.format(self.host, e))
        except CancelledError as e:
            log.error('Canceled connection to {} ()'.format(self.host, e))
        except Exception as e2:
            log.exception('Failed to retrieve "{}" ({})'.format(self.host, e2))
        returnValue(result)

    @inlineCallbacks
    def get(self, data=None, archive=False):
        result = yield self._request(data)
        if result is not None:
            # save output to file
            if archive:
                try:
                    filename = '/tmp/%s.xml' % time.time()
                    print "writing %s" % filename
                    self.write_data(filename, result)
                except Exception as e:
                    log.exception('Error writing output "{}" ({})'.format(str(result), e))
            # return cleaned XML
            try:
                returnValue(self.xml_cleanup(result))
            except Exception as e:
                log.exception('Error returning output "{}" ({})'.format(str(result), e))
        # Should not happen
        returnValue(None)

    def xml_cleanup(self, response):
        '''ILO XML doesn't comply to standard, so changing it from:

                <?xml version="1.0"?>
                <RIBCL VERSION="2.22">
                <RESPONSE
                    STATUS="0x0000"
                    MESSAGE='No error'
                     />
                </RIBCL>
                <?xml version="1.0"?>
                <RIBCL VERSION="2.22">
                <RESPONSE
                    STATUS="0x0000"
                    MESSAGE='No error'
                     />
                </RIBCL>

            to:

                <RIBCLS>
                <RIBCL VERSION="2.22">
                <RESPONSE
                    STATUS="0x0000"
                    MESSAGE='No error'
                     />
                </RIBCL>
                <RIBCL VERSION="2.22">
                <RESPONSE
                    STATUS="0x0000"
                    MESSAGE='No error'
                     />
                </RIBCL>
                </RIBCLS>
        '''
        response = str(response)
        response = response.replace('<?xml version="1.0"?>', '')
        # encapsulating multiple <RIBCL> documents in output
        return '<RIBCLS>{}</RIBCLS>'.format(response)

    def write_data(self, filename, data):
        '''write out data to the provided filename'''
        f = open(filename, 'w')
        f.write(data)
        f.close()


def print_and_stop(output, client):
    '''debug method for output'''
    print '=' * 80
    try:
        xml_result = client.xml_cleanup(output)
        print xml_result
    except Exception as e:
        print e
    if reactor.running:
       reactor.stop()


if __name__ == '__main__':
    client = ILO2ProtocolHandler('10.4.100.140', 443, 'ilomon', '')
    d = client.test_request()
    d.addCallback(print_and_stop, client)
    reactor.run()
