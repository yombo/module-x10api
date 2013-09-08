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

The Yombo team and other contributors hopes that it will be useful, but
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

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>
:license: GPL(v3)
"""
import time
import re

from yombo.core.exceptions import ModuleWarning
from yombo.core.helpers import getComponent, getInterfaceModule
from yombo.core.log import getLogger
from yombo.core.module import YomboModule

logger = getLogger("moduls.x10api")

class X10Cmd:
    """
    An x10 command instance that is passed between this module
    and any interface modules to send X10 commands to the power line.
    """
    def __init__(self, x10api, message):
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
        self.x10uuid = message.msgUUID
        """@ivar: The msgID that was generated to create this command. Is None if comming from interface module.
           @type: C{str}"""
        self.x10extended = None
        """@ivar: Extended data to send with the x10 command.
           @type: C{hex}"""
        self.x10status = None
        """@ivar: The updated state of the device. This is set by the interface module.
           @type: C{str} or C{int}"""
        self.created = time.time()
        self.interfaceResult = None
        self.commandResult = None
        self.x10api = x10api
        self.originalMessage = message
        self.deviceobj = message.payload['deviceobj']

    def dump(self):
        """
        Convert key class contents to a dictionary.

        :return: A dictionary of the key class contents.
        :rtype: dict
        """
        return {'x10house': self.x10house,
                'x10number': self.x10number,
                'x10command': self.x10command,
                'created': self.created,
                'interfaceResult': self.interfaceResult,
                'commandResult': self.commandResult }
                
    def sendCmdToInterface(self):
        """
        Send to the x10 command module
        """
        self.x10api.interfaceModule.sendX10Cmd(self)
        
    def statusReceived(self, status, statusExtended={}):
        """
        Contains updated status of a device received from the interface.
        """
        pass
       
    def done(self):
        """
        Called by the interface module once the command has been completed.
        
        Note: the interface module will call the X10api module when a device
        has a status change.  This is a different process then a command.
        """
        self.x10api.cmdDone(self)
        self.x10api.removeX10Cmd(self)

    def pending(self):
        """
        Called by the interface module when command is still pending.
        Interface module must call this if processing takes longer than 1
        second.
        """
        reply = self.originalMessage.getReply(msgStatus='processing', msgStatusExtra="interface module processing request")
        reply.send()
    
    def failed(self, statusmsg):
        """
        Used to tell the sending module that the command failed.
        
        statusmsg should hold the failure reason.  Displayed to user.
        """
        reply = self.originalMessage.getReply(msgStatus='failed', msgStatusExtra="interface module failed to process request")
        self.x10api.removeX10Cmd(self)
        reply.send()

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

        self.x10cmds = {}         #store a copy of active x10cmds
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
        
        self.deviceTypes = {
          'jmtHRMTHn3LwvzeTU2pZrTQk' : "x10Appliance",
          'aSepfx4y5Pfav4XSi5MYujhi' : "x10Lamp",
          'fcA4d0WZHiyGJkdmQ8PwfJ7e' : "HouseCode",
          }

        self.x10devices = {} # used to lookup house/unit to a device
        for devkey, device in self._LocalDevices.iteritems():
            house = device.deviceVariables['housecode'][0].upper()
            unit = int(device.deviceVariables['unitnumber'][0])
            if house not in self.x10devices:
              self.x10devices[house] = {}
            self.x10devices[house][unit] = device

    def load(self):
        self.interfaceModule = getComponent(getInterfaceModule(self))
    
    def start(self):
        pass
        
    def stop(self):
        pass

    def unload(self):
        pass

    def message(self, message):
#        logger.debug("X10 got message: %s", message.dump())
        if message.msgType == 'cmd' and message.msgStatus == 'new':
            if message.payload['deviceobj'].deviceUUID in self._LocalDevices:
                try:
                  self.processNewCmdMsg(message)
                except:
                    logger.info("X10 message caught something.")

    def processNewCmdMsg(self, message):
        logger.debug("msg: %s", message.dump())

        x10cmd = X10Cmd(self, message)

        housecode = x10cmd.deviceobj.deviceVariables['housecode'][0].upper()
        if bool(re.match('[A-P]', housecode)) == False:
            raise ModuleWarning("Device dosn't have a valid house number.", 100, self)

        unitnumber = x10cmd.deviceobj.deviceVariables['unitnumber'][0]
        try:
            unitnumber = int(unitnumber)
            if unitnumber < 1 or unitnumber > 16:
              raise ModuleWarning("Device dosn't have a valid unit number.", 101, self)
        except:
              raise ModuleWarning("Device dosn't have a valid unit number.", 101, self)

        logger.info("House address: item %s - %s  'HU'" % (housecode, unitnumber))        

        x10cmd.x10house = { 
          "value"    : housecode,
          "x10string": self.houseToX10[housecode]['string'],
          "x10hex"   : self.houseToX10[housecode]['hex'] }
          
        x10cmd.x10number = { 
          "value"    : unitnumber,
          "x10string": self.deviceToX10[unitnumber]['string'],
          "x10hex"   : self.deviceToX10[unitnumber]['hex'] }

        x10cmd.x10command = {
          "origcmdobj" : message['payload']['cmdobj'],
          "value"      : message['payload']['cmdobj'].cmd.upper(),
          "x10hex"     : self.functionToX10[message['payload']['cmdobj'].cmd.upper()]}

        self.x10cmds[message.msgUUID] = x10cmd
        logger.debug("NEW: x10cmd: %s", x10cmd.dump())

        self.interfaceModule.sendX10Cmd(x10cmd)

    def statusUpdate(self, house, unit, command, status=None):
        """
        Called by interface modules when a device has a change of status.
        """
        unit = int(unit)
        if house in self.x10devices and unit in self.x10devices[house]:
          device =  self.x10devices[house][unit]
          newstatus = None
          tempcmd = command.upper()

          if device.deviceTypeUUID == "jmtHRMTHn3LwvzeTU2pZrTQk": # appliance
            if tempcmd == 'ON':
              newstatus = 'ON'
            elif tempcmd == 'OFF':
              newstatus = 'OFF'
          elif device.deviceTypeUUID == "aSepfx4y5Pfav4XSi5MYujhi": # basic lamp
            if tempcmd == 'ON':
              newstatus = 100
            elif tempcmd == 'OFF':
              newstatus = 0
            elif tempcmd == 'DIM':
              if type(device.status[0]['status']) is int:
                  newstatus = device.status[0]['status'] - 12
              else:
                  newstatus = 88
            elif tempcmd == 'BRIGHT':
              if type(device.status[0]['status']) is int:
                  newstatus = device.status[0]['status'] + 12
              else:
                  newstatus = 100

            if type(newstatus) is int:
              if newstatus > 100:
                  newstatus = 100
              elif newstatus < 0:
                  newstatus = 0
            else:
                newstatus = 0

          logger.info("status update... %s" % newstatus)
          device.setStatus(status=newstatus, source="x10api")

    def cmdDone(self, x10cmd):
        """
        Called after interface module reports the command was sent out.
        
        First update the device status value, then sent a cmdreply msg.
        Finally, send a status message.
        """
        replmsg = x10cmd.originalMessage.getReply(status='done', statusExtra="Command completed.")
        logger.info("msgreply: %s", replmsg.dump())
        replmsg.send()

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

