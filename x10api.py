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
import sys
import traceback

from yombo.core.exceptions import YomboModuleWarning
from yombo.core.helpers import getComponent, getInterfaceModule
from yombo.core.log import getLogger
from yombo.core.module import YomboModule

logger = getLogger("modules.x10api")

class X10Cmd:
    """
    An x10 command instance that is passed between this module
    and any interface modules to send X10 commands to the power line.
    """
    def __init__(self, apimodule, message):
        """
        Setup the class to communicate between x10 API module and any interface modules.
        
        :param x10api: A pointer to the x10api class.
        """
#        self.callAfterChange = [] #is this needed?
#        self.callBeforeChange = []
        self.deviceobj = message.payload['deviceobj']
        """@ivar: The device itself
           @type: C{YomboDevice}"""
        self.cmdobj = message.payload['cmdobj']
        """@ivar: The command itself
           @type: C{YomboDevice}"""
        self.deviceClass = "x10"

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
        self.msguuid = message.msgUUID
        """@ivar: The msgID that was generated to create this command. Is None if comming from interface module.
           @type: C{str}"""
        self.extended = None
        """@ivar: Extended data to send with the x10 command.
           @type: C{hex}"""
        self.deviceState = None
        """@ivar: The updated state of the device. This is set by the interface module.
           @type: C{str} or C{int}"""
        self.created = time.time()
        self.interfaceResult = None
        self.commandResult = None
        self.apimodule = apimodule
        self.originalMessage = message

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
        self.apimodule.interfaceModule.sendX10Cmd(self)
        
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
        replymsg = self.originalMessage.getReply(msgStatus='done', statusExtra="Command completed.")
        logger.info("msgreply: {replymsg}", replymsg=replymsg.dump())
        replymsg.send()
        self.apimodule.removeX10Cmd(self)

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
        self.apimodule.removeX10Cmd(self)
        reply.send()

class X10API(YomboModule):
    """
    X10 Command Module
    
    Generic module that handles all x10 commands from other modules an
    prepares it for an interface module.  Also receives data from
    interface modules for delivery to other gateway modules.
    """

    def _init_(self):
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

        self.x10devices = {} # used to lookup house/unit to a device

    def _load_(self):
        try:
            interfaceModule = self._DeviceTypes.itervalues().next()  # Just get any deviceType as they all are routed to the same interface module
            self.interfaceModule = self._ModulesLibrary.getDeviceRouting(interfaceModule[0]['devicetypeuuid'], 'Interface', 'module')
            self.interfaceSupport = True
            self._reload_()
        except:
            # no X10API module!
            logger.warn("Insteon API - No Insteon interface module found, disabling Insteon support.")
            self.interfaceSupport = False
        logger.debug("X10 API - Interface module: {x10interface}", x10interface=self.interfaceModule)

    def _reload_(self):
        if self.interfaceSupport:
            self.x10devices.clear()
            for devkey, device in self._Devices.iteritems():
                logger.info("devicevariables: {vars}", vars=device.deviceVariables)
                house = device.deviceVariables['house']['value'][0].upper()
                unit = int(device.deviceVariables['unitnumber']['value'][0])
                if house not in self.x10devices:
                  self.x10devices[house] = {}
                self.x10devices[house][unit] = device
                item = "%s%s" % (house, str(unit))
                self.x10devices[item] = device

    def _start_(self):
        pass
        
    def _stop_(self):
        pass

    def _unload_(self):
        pass

    #todo
    def _UpdateDeviceTypes_(self, oldDeviceType, newDeviceType):
        pass

    def message(self, message):
        """
        Receives a message from the Yombo Framework.
        :param message: A Yombo Framework Message
        :return: None
        """
        if message.msgType == 'cmd' and message.msgStatus == 'new':
            logger.warn("bb {deviceTypes}", deviceTypes=message.payload['deviceobj'])
            if message.payload['deviceobj'].deviceTypeUUID in self._DeviceTypes:
                try:
                    self.processNewCmdMsg(message)
                except:
                    logger.error("1:: {e}", e=sys.exc_info())
                    logger.error("---------------==(Traceback)==--------------------------")
                    logger.error("{e}", e=traceback.print_exc(file=sys.stdout))
                    logger.error("--------------------------------------------------------")

    def processNewCmdMsg(self, message):
        """
        Sent from message to process an X10 command.
        :param message:
        :return:
        """
        logger.debug("in x10api::processNewCmdMsg")

        x10cmd = X10Cmd(self, message)

        house = x10cmd.deviceobj.deviceVariables['house']['value'][0].upper()
        if bool(re.match('[A-P]', house)) == False:
            raise YomboModuleWarning("Device dosn't have a valid house number.", 100, self)

        unitnumber = x10cmd.deviceobj.deviceVariables['unitnumber']['value'][0]
        try:
            unitnumber = int(unitnumber)
            if unitnumber < 1 or unitnumber > 16:
              raise YomboModuleWarning("Device dosn't have a valid unit number.", 101, self)
        except:
              raise YomboModuleWarning("Device dosn't have a valid unit number.", 101, self)

        logger.info("House address: item {house} - {unitnumber} 'HU'", house=house, unitnumber=unitnumber)

        x10cmd.x10house = { 
          "value"    : house,
          "x10string": self.houseToX10[house]['string'],
          "x10hex"   : self.houseToX10[house]['hex'] }
          
        x10cmd.x10number = { 
          "value"    : unitnumber,
          "x10string": self.deviceToX10[unitnumber]['string'],
          "x10hex"   : self.deviceToX10[unitnumber]['hex'] }

        x10cmd.x10command = {
          "origcmdobj" : message['payload']['cmdobj'],
          "value"      : message['payload']['cmdobj'].cmd.upper(),
          "x10hex"     : self.functionToX10[message['payload']['cmdobj'].cmd.upper()]}

        self.x10cmds[message.msgUUID] = x10cmd
        logger.debug("NEW: x10cmd: {x10cmd}", x10cmd=x10cmd.dump())

#        x10cmd.deviceobj.getRouting('interface')
#        self._ModulesLibrary.getDeviceRouting(x10cmd.deviceobj.deviceTypeUUID, 'Interface')
        self.interfaceModule.sendX10Cmd(x10cmd)

    def statusUpdate(self, house, unit, command, status=None, deviceObj=None):
        """
        Called by interface modules when a device has a change of status.
        """
        logger.warn("x10api - status update: {house}{unit}:{command}", house=house, unit=unit, command=command)
        unit = int(unit)
        if deviceObj is None:
            if house in self.x10devices and unit in self.x10devices[house]:
              deviceObj =  self.x10devices[house][unit]

        newstatus = None
        tempcmd = command.upper()

#        self._DevicesByType('x10_appliance')
        logger.warn("self._DevicesByType('x10_appliance'): {dt}", dt=self._DevicesByType('x10_appliance'))
        logger.warn("deviceObj.deviceTypeLabel: {dt}", dt=deviceObj.deviceTypeLabel)
        if deviceObj.deviceTypeLabel == 'x10_appliance':
            logger.warn("in x10 appliance")
            if tempcmd == 'ON':
                newstatus = 'ON'
            elif tempcmd == 'OFF':
                newstatus = 'OFF'
        elif deviceObj.deviceTypeLabel == 'x10_lamp': # basic lamp
            logger.warn("in x10 lamp")
            if tempcmd == 'ON':
                newstatus = 100
            elif tempcmd == 'OFF':
                newstatus = 0
            elif tempcmd == 'DIM':
                if type(deviceObj.status[0]['status']) is int:
                    newstatus = deviceObj.status[0]['status'] - 12
                else:
                    newstatus = 88
            elif tempcmd == 'BRIGHT':
                if type(deviceObj.status[0]['status']) is int:
                    newstatus = deviceObj.status[0]['status'] + 12
                else:
                    newstatus = 100

            if type(newstatus) is int:
                if newstatus > 100:
                    newstatus = 100
                elif newstatus < 0:
                    newstatus = 0
            else:
                newstatus = 0

        logger.info("status update... {newstatus}", newstatus=newstatus)
        deviceObj.setStatus(status=newstatus, source="x10api")
    
    def removeX10Cmd(self, x10cmd):
        """
        Delete an old x10cmd object
        """
        logger.debug("Purging x10cmd object: {x10cmd}", x10cmd=x10cmd.x10uuid)
        del self.x10cmds[x10cmd.msguuid]
        logger.debug("pending x10cmds: {x10cmds}", x10cmds=self.x10cmds)

