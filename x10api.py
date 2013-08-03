#This file was created by Yombo for use with Yombo Gateway automation
#software.  Details can be found at http://www.yombo.net
"""
X10 API
===========

Provides API interface for X10 control.

License
=======

This module is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The B{Yombo} team and other contributors hopes that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

The GNU General Public License can be found here: http://www.gnu.org/licenses

Plugin purpose
==============

This module provides command interface for X10 devices.  It will forward
any x10 requests to any attached x10 interface module.  It will also
process any status updates and send to the rest of the Yombo gateway modules.

Implements
==========

- class X10Cmd - A class to pass between X10API module and interface modules.
- class X10API - the command module 

:author: Mitch Schwenk <mitch-gw@yombo.net>
:license: GPL(v3)

"""
import time
import re

from yombo.core.module import YomboModule
from yombo.core.helpers import getComponent, getInterfaceModule, getDevices
from yombo.core.db import get_dbtools
from yombo.core.log import getLogger

logger = getLogger()

class X10Cmd:
    """
    An x10 command instance that is passed between this module
    and any interface modules to send X10 commands to the power line.
    """
    def __init__(self, x10api, message = {'msgID':None}):
        """
        Setup the class to communicate between x10 API module and any interface modules.
        
        :param x10api: A pointer to the x10api class.
        """
#        self.callAfterChange = [] #is this needed?
#        self.callBeforeChange = []

        self.x10house = None
        """@ivar: Information regarding the house letter. "value" will be the house letter. x10string and x10hex
             represent the X10 code to send in either string or hex format.
           @type: C{dict}"""
        self.x10number = None
        """@ivar: Information regarding the unit number. "value" will be the unit number. x10string and x10hex
             represent the X10 code to send in either string or hex format.
           @type: C{dict}"""
        self.x10command = None
        """@ivar: Information regarding the command. "origcmd" is the original command. "value" is the offical
             x10 command, and x10hex is the offical x10 hex command code.
           @type: C{dict}"""
        self.x10uuid = message.msgID
        """@ivar: The msgID that was generated to create this command. Is None if comming from interface module.
           @type: C{str}"""
        self.x10extended = None
        """@ivar: Extended data to send with the x10 command.
           @type: C{hex}"""
        self.x10value = None
        """@ivar: The updated state of the device. This is set by the interface module.
           @type: C{str} or C{int}"""
        self.chain = {}  # AKA history
        self.created = int(time.time())
        self.interfaceResult = None
        self.commandResult = None
        self.x10api = x10api
        self.originalMessage = message
        self.deviceid = None
        
    def dump(self):
        """
        Convert key class contents to a dictionary.

        @return: A dictionary of the key class contents.
        @rtype: C{dict}
        """
        return {'x10house': self.x10house,
                'x10number': self.x10number,
                'x10command': self.x10command,
                'chain': self.chain,
                'created': self.created,
                'interfaceResult': self.interfaceResult,
                'commandResult': self.commandResult }
                
    def sendCmdToInterface(self):
        """
        Send to the x10 command module
        """
        
    def statusReceived(self, status, statusExtended={}):
        """
        Contains updated status of a device received from the interface.
        """
        pass
        
    def cmdDone(self):
        """
        Every command should tell the sender when the command was sent.
        
        We just need to validate that it was sent, some protocols are
        only one way.  This way the user gets some feedback.
        
        In this case, X10 may not work, but at the command was issued.
        """
        self.x10api.cmdDone(self)
        self.x10api.removeX10Cmd(self)

    def cmdPending(self):
        """
        Used to tell the sending module that the command is pending (processing)
        """
        pass
    
    def cmdFailed(self, statusmsg):
        """
        Used to tell the sending module that the command failed.
        
        statussg should hold the failure reason.  Displayed to user.
        """
        pass

class X10API(YomboModule):
    """
    X10 Command Module
    
    Generic module that handles all x10 commands from other modules an
    prepares it for an interface module.  Also recieves data from
    interface modules for delivery to other gateway modules.
    """
#    zope.interface.implements(IModule)

    def init(self):
        self._ModDescription = "X10 Command Module"
        self._ModAuthor = "Mitch Schwenk @ Yombo"
        self._ModUrl = "http://www.yombo.net"

        self.register_distributions = ['cmd']
        self.devices = getDevices()

        self.x10cmds = {}         #store a copy of active x10cmds
        self.dbtools = get_dbtools()
        self.originalMessage = None
        self.houseToX10 = {
          'A' : {'string' : '6', 'hex' : 0x06},
          'B' : {'string' : 'E', 'hex' : 0x0E},
          'C' : {'string' : '2', 'hex' : 0x02},
          'D' : {'string' : 'A', 'hex' : 0x0A},
          'E' : {'string' : '1', 'hex' : 0x01},
          'F' : {'string' : '9', 'hex' : 0x09},
          'G' : {'string' : '5', 'hex' : 0x05},
          'H' : {'string' : 'D', 'hex' : 0x0D},
          'I' : {'string' : '7', 'hex' : 0x07},
          'J' : {'string' : 'F', 'hex' : 0x0F},
          'K' : {'string' : '3', 'hex' : 0x03},
          'L' : {'string' : 'B', 'hex' : 0x0B},
          'M' : {'string' : '0', 'hex' : 0x00},
          'N' : {'string' : 'N', 'hex' : 0x08},
          'O' : {'string' : '4', 'hex' : 0x04},
          'P' : {'string' : 'C', 'hex' : 0x0C}  }
          
        self.deviceToX10 = {
          1 :  {'string' : '6', 'hex' : 0x06},
          2 :  {'string' : 'E', 'hex' : 0x0E},
          3 :  {'string' : '2', 'hex' : 0x02},
          4 :  {'string' : 'A', 'hex' : 0x0A},
          5 :  {'string' : '1', 'hex' : 0x01},
          6 :  {'string' : '9', 'hex' : 0x09},
          7 :  {'string' : '5', 'hex' : 0x05},
          8 :  {'string' : 'D', 'hex' : 0x0D},
          9 :  {'string' : '7', 'hex' : 0x07},
          10 : {'string' : 'F', 'hex' : 0x0F},
          11 : {'string' : '3', 'hex' : 0x03},
          12 : {'string' : 'B', 'hex' : 0x0B},
          13 : {'string' : '0', 'hex' : 0x00},
          14 : {'string' : 'N', 'hex' : 0x08},
          15 : {'string' : '4', 'hex' : 0x04},
          16 : {'string' : 'C', 'hex' : 0x0C}  }

        self.functionToX10 = {
          'HOUSE_OFF'     : 0x00,
          'HOUSE_ON'      : 0x01,
          'ON'            : 0x02,
          'OFF'           : 0x03,
          'DIM'           : 0x04,
          'BRIGHTEN'      : 0x05,
          'MICRO_DIM'     : None,
          'MICRO_BRIGHTEN': None,
          'HOUSE_LIGHTS_OFF': 0x06,
          'EXTENDED_CODE' : 0x07,
          'HAIL_REQUEST'  : 0x08,
          'HAIL_ACK'      : 0x09,
          'PRESET_DIM1'   : 0x0A,
          'PRESET_DIM2'   : 0x0B,
          'EXTENDED_DATA' : 0x0C,
          'STATUS_ON'     : 0x0D,
          'STATUS_OFF'    : 0x0E,
          'STATUS_REQUEST': 0x0F }

        self._housecodes = list('ABCDEFGHIJKLMNOP')
        self._unitcodes = range(1, 17)
        
#@todo: create irigation, alarm, etc types.
        self.deviceTypes = {
          1 : "x10Appliance",
          2 : "x10Lamp"}        

        self.moduleDeviceTypes = [4,5,11]  #  purpose???
        
#@todo: get devicetypecommand mappings from database
            
    def load(self):
#TODO: move to reading config
#        self.interfaceModule = 'yombo.modules.Homevision'
        logger.debug("@#@#@#@#@#@#@#@:  %s", getInterfaceModule(self))
#        self.interfaceModule = 'yombo.modules.X10Heyu'
        
        self.interfaceModule = getComponent(getInterfaceModule(self))
    
    def start(self):
        logger.debug("X10 API command module started") 
        
    def stop(self):
        pass

    def unload(self):
        pass

    def message(self, message):
#        logger.debug("X10 got message: %s", message.dump())
        if message.msgType == 'cmd' and message.msgStatus == 'new':
            deviceid = message['payload']['deviceid']
            if self.devices[deviceid].devicetypeid in self.deviceTypes:
                self.processNewCmdMsg(message)

    def processNewCmdMsg(self, message):
        logger.debug("msg: %s", message.dump())

        x10cmd = X10Cmd(self, message)
        x10cmd.deviceid = message['payload']['deviceid']

        address = self.devices[message['payload']['deviceid']].deviceaddress
        p = re.compile("([a-zA-Z])([0-9]*)")
        addy = house = number = None
        logger.debug("House address pre: %s length: %s" % (address, len(address)))        
        for addy in p.findall(address):
            house = addy[0].upper()
            if len(address) > 1:
                number = int(addy[1])
            else:
                number = 1
                address = address + str(1)

        logger.trace("House address: item %s - %s  'HU'" % (house, number))        

        if not ( house in self._housecodes and int(number) in self._unitcodes):
            logger.warning("Invalid item %s - %s, must be 'HU'" % (addy[0], addy[1]))        

#TODO: Respond with message that command is invalid for a reason...                    

        x10cmd.x10house = { 
          "value"    : house,
          "x10string": self.houseToX10[house]['string'],
          "x10hex"   : self.houseToX10[house]['hex'] }
          
        x10cmd.x10number = { 
          "value"    : number,
          "x10string": self.deviceToX10[number]['string'],
          "x10hex"   : self.deviceToX10[number]['hex'] }

        x10cmd.x10command = {
          "origcmd" : message['payload']['cmd'],
          "value": self.functionToX10[message['payload']['cmd'].upper()],
          "x10hex": self.functionToX10[message['payload']['cmd'].upper()] }

        self.x10cmds[message.msgID] = x10cmd
        logger.debug("NEW: x10cmd: %s", x10cmd.dump())

        self.interfaceModule.sendX10Cmd(message.msgID)

    def statusReceived(self, x10cmd):
        """
        Used to deliver device state changes. A lamp turns on, etc.

        Since the majority of the status' generated are actually X10 controllers, these
        are actually commands. The value of payload will be the final state value of
        the X10 device.

        Two messages will be generated: a "new" command message and a status message.
        """
        pass

    
    def cmdDone(self, x10cmd):
        """
        Called after interface module reports the command was sent out.
        
        First update the device status value, then sent a cmdreply msg.
        Finally, send a status message.
        """
        tempcmd = x10cmd.x10command
        deviceid = x10cmd.deviceid
        newstatus = None
#@todo: Move to interface module!!!
        if tempcmd == 'on':
            newstatus = 100
        elif tempcmd == 'off':
            newstatus = 'off'
        elif tempcmd == 'dim':
            if type(self.devices[deviceid].status[0]) is int:
                newstatus = self.devices[deviceid].status[0] - 12
            else:
                newstatus = 88
        elif tempcmd == 'bright':
            if type(self.devices[deviceid].status[0]) is int:
                newstatus = self.devices[deviceid].status[0] + 12
            else:
                newstatus = 100
            
        if type(newstatus) is int:
            if newstatus > 100:
                newstatus = 100
            elif newstatus < 0:
                newstatus = 0
                
        self.devices[deviceid].setStatus(silent=True, status=newstatus)

        # 1 - reply to sender so they know we are done.
        replmsg = x10cmd.originalMessage.getReply()
        replmsg.msgStatusExtra = 'done'
        replmsg.payload = {'status'  : self.devices[deviceid].status,
                           'cmd'     : x10cmd.x10command['origcmd'],
                           'deviceid': x10cmd.deviceid }
        logger.debug("msgreply: %s", replmsg.dump())
        replmsg.send()

        # 2 - let the rest of the world know.
        self.devices[deviceid].sendStatus(src=self.fname)

    def cmdPending(self, x10cmd, statusmsg):
        """
        Used to tell the sending module that the command is pending.
        
        Used when it's taking longer than 1 second.  This lets the other
        module/client/device know we received the command, but it's still
        processing.
        
        A cmdDone or cmdFail is expected afterward.
        
        Statusmsg should contain the actual status to display to a user
        or to report in a log.
        """
        pass

    def cmdFailed(self, x10cmd, statusmsg="Unknown reason."):
        """
        Used to tell the sending module that the command has failed.
        
        statusmsg should contain the status messsage to display to user
        or enter on a log file.
        """
        pass
    
    def removeX10Cmd(self, x10cmd):
        """
        Delete an old x10cmd object
        """
        logger.debug("Purging x10cmd object: %s", x10cmd.x10uuid)
        del self.x10cmds[x10cmd.x10uuid]
        logger.debug("pending x10cmds: %s", self.x10cmds)

