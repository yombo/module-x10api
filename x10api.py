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
from collections import OrderedDict

# Import twisted libraries
from twisted.internet.defer import inlineCallbacks

from yombo.core.exceptions import YomboModuleWarning, YomboWarning
from yombo.core.log import get_logger
from yombo.core.module import YomboModule
from yombo.utils import percentage, global_invoke_all

logger = get_logger("modules.x10api")

class X10Cmd:
    """
    An x10 command instance that is passed between this module
    and any interface modules to send X10 commands to the power line.
    """
    def __init__(self, apimodule, request_id, device, command):
        """
        Setup the class to communicate between x10 API module and any interface modules.
        
        :param x10api: A pointer to the x10api class.
        """
        self._FullName = 'yombo.gateway.modules.X10API.X10Cmd'
        self._Name = 'X10API.X10Cmd'
#        self.callAfterChange = [] #is this needed?
#        self.callBeforeChange = []
        self.deviceobj = device
        """@ivar: The device itself
           @type: C{YomboDevice}"""
        self.cmdobj = command
        """@ivar: The command itself
           @type: C{YomboDevice}"""
        self.deviceClass = "x10"

        self.x10_house = None
        """@ivar: Information regarding the house letter. "value" will be the house letter. x10string and x10hex
             represent the X10 code to send in either string or hex format.
           @type: C{dict}"""
        self.x10_number = None
        """@ivar: Information regarding the unit number. "value" will be the unit number. x10string and x10hex
             represent the X10 code to send in either string or hex format.
           @type: C{dict}"""
        self.x10_command = None
        """@ivar: Information regarding the command. "origcmd" is the original command. "value" is the offical
             x10 command, and x10hex is the offical x10 hex command code.
           @type: C{dict}"""
        self.request_id = request_id
        """@ivar: The request_id that was generated to create this command. Is None if comming from interface module.
           @type: C{str}"""
        self.extended = None
        """@ivar: Extended data to send with the x10 command.
           @type: C{hex}"""
        self.created_at = time.time()
        self.interfaceResult = None
        self.commandResult = None
        self.apimodule = apimodule

    def dump(self):
        """
        Convert key class contents to a dictionary.

        :return: A dictionary of the key class contents.
        :rtype: dict
        """
        return {'x10_house': self.x10_house,
                'x10_number': self.x10_number,
                'x10_command': self.x10_command,
                'created_at': self.created_at,
                'interfaceResult': self.interfaceResult,
                'commandResult': self.commandResult,
                'request_id': self.request_id}
                
    def send_command_to_interface(self):
        """
        Send to the x10 command module
        """
        self.apimodule.interface_callback.sendX10Cmd(self)
        
    def status_received(self, status, statusExtended={}):
        """
        Contains updated status of a device received from the interface.
        """
        raise YomboWarning("X10 received a status, but didn't pass it on!!", 300, 'status_received', 'X10Cmd')
       
    def done(self):
        """
        Called by the interface module once the command has been completed.
        
        Note: the interface module will call the X10api module when a device
        has a status change.  This is a different process then a command.
        """
        device_status = {
            'human_status': self.cmdobj.label,
            'machine_status': self.cmdobj.machine_label,
            'source': self,
        }
        self.deviceobj.device_command_done(self.request_id)
        self.deviceobj.set_status(**device_status)  # set and send the status of the x10 device
        self.apimodule.remove_x10_command(self)

    def command_pending(self):
        """
        Called by the interface module when command is still pending.
        Interface module must call this if processing takes longer than 1
        second.
        """
        self.deviceobj.device_command_pending(self.request_id, message=_('modules.x10api', 'Waiting on X10 interface.'))

    def command_failed(self, statusmsg):
        """
        Used to tell the sending module that the command failed.
        
        statusmsg should hold the failure reason.  Displayed to user.
        """
        self.deviceobj.device_command_failed(self.request_id,
                                             message=_('modules.x10api',
                                                       'Interface module failed to process the request.'))
        self.apimodule.remove_x10_command(self)

class X10API(YomboModule):
    """
    X10 Command Module
    
    Generic module that handles all x10 commands from other modules an
    prepares it for an interface module.  Also receives data from
    interface modules for delivery to other gateway modules.
    """

    def _init_(self, **kwargs):
        self._ModDescription = "X10 Command Module"
        self._ModAuthor = "Mitch Schwenk @ Yombo"
        self._ModUrl = "http://www.yombo.net"

        self.x10cmds = {}         #store a copy of active x10cmds
        self.house_to_x10 = {
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
          
        self.unit_number_to_x10 = {
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

        self.command_to_x10 = {
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

        self.x10_devices = {} # used to lookup house/unit to a device
        self.interface_found = False

    @inlineCallbacks
    def _load_(self, **kwargs):
        """
        Sets up the module to start processng X10 commands. After this function is complete, the X10 API module will
        be ready to accept commands.

        **Hooks implemented**:

        * hook_x10api_interfaces : Expects a dictionary back with "priority" and "callback" for any modules that
          can send X10 commands to the power lines. Since only one module can perform this task, the module with the
          highest priority (highest number) will be used. *callback* is the function to call to perform this request.

        :param kwargs:
        :return:
        """
        results = yield global_invoke_all('x10api_interfaces', called_by=self)
        temp = {}
#        logger.debug("message: automation_sources: {automation_sources}", automation_sources=automation_sources)
        for component_name, data in results.items():
            temp[data['priority']] = {'name': component_name, 'callback':data['callback']}

        interfaces = OrderedDict(sorted(temp.items()))
        self.interface_callback = None
        if len(interfaces) == 0:
            logger.warn("X10 API - No X10 Interface module found, disabling X10 support.")
        else:
            self.interface_found = True
            key = list(interfaces.keys())[-1]
            self.interface_callback = temp[key]['callback']  # we can only have one interface, highest priority wins!!
        # logger.warn("X10 interface: {interface}", interface=self.interface_callback)

        if self.interface_callback is not None:
            self.x10_devices.clear()
            # print "x10api init1!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!114"
            # print "x10api devices: %s" % devices
            module_devices = yield self._module_devices()
            for device_id, device in module_devices.items():
                try:
                    device = self._Devices[device_id]
                    # logger.debug("devicevariables: {vars}", vars=device.device_variables_cached)
                    house = device.device_variables_cached['house']['values'][0].upper()
                    unit = int(device.device_variables_cached['unit_code']['values'][0])
                except:
                    continue
                if house not in self.x10_devices:
                  self.x10_devices[house] = {}
                self.x10_devices[house][unit] = device
                item = "%s%s" % (house, str(unit))
                self.x10_devices[item] = device

    def _start_(self, **kwargs):
        pass
        
    def _stop_(self, **kwargs):
        pass

    def _unload_(self, **kwargs):
        pass

    def _module_devicetypes_(self, **kwargs):
        return ['x10_lamp', 'x10_appliance']

    def _device_command_(self, **kwargs):
        """
        Received a request to do perform a command for a device.
        :param kwags: Contains 'device' and 'command'.
        :return: None
        """
        logger.debug("X10 API received device_command: {kwargs}", kwargs=kwargs)
        device = kwargs['device']
        request_id = kwargs['request_id']
        if self.interface_found is False:
            logger.info("X10 API received a command, but has no interfaces to send to. Try enabling an X10 interface module.")
            device.device_command_failed(request_id, message=_('module.x10api', 'X10 API received a command, but has no interfaces to send to. Try enabling an X10 interface module.'))
            return

        if device.device_type_id not in self._module_device_types_cached:
            return  # not meant for us.

        device.device_command_received(request_id, message=_('module.x10api', 'Handled by X10API module.'))

        command = kwargs['command']

        x10cmd = X10Cmd(self, request_id, device, command)

        # print("device vars: %s" % x10cmd.deviceobj.device_variables_cached)
        house = x10cmd.deviceobj.device_variables_cached['house']['values'][0].upper()
        if bool(re.match('[A-P]', house)) == False:
            raise YomboModuleWarning(_('module.x10api', "Device dosn't have a valid house code."), 100, self)

        unitnumber = x10cmd.deviceobj.device_variables_cached['unit_code']['values'][0]
        try:
            unitnumber = int(unitnumber)
            if unitnumber < 1 or unitnumber > 16:
              raise YomboModuleWarning(_('module.x10api', "Device dosn't have a valid unit number."), 101, self)
        except:
              raise YomboModuleWarning(_('module.x10api', "Device dosn't have a valid unit number."), 101, self)

#        logger.debug("House address: item {house} - {unitnumber} 'HU'", house=house, unitnumber=unitnumber)

        x10cmd.x10_house = { 
          "value"    : house,
          "x10string": self.house_to_x10[house]['string'],
          "x10hex"   : self.house_to_x10[house]['hex']
        }

        x10cmd.x10_number = { 
          "value"    : unitnumber,
          "x10string": self.unit_number_to_x10[unitnumber]['string'],
          "x10hex"   : self.unit_number_to_x10[unitnumber]['hex']
        }

        x10cmd.x10_command = {
          "value"      : command.cmd.upper(),
          "x10hex"     : self.command_to_x10[command.cmd.upper()]
        }

        self.x10cmds[request_id] = x10cmd
        logger.debug("NEW: x10cmd: {x10cmd}", x10cmd=x10cmd.dump())

        self.interface_callback(x10cmd)

    def status_update(self, house, unit, command, status=None, deviceObj=None):
        """
        Called by interface modules when a device has a change of status.
        """
        logger.info("x10api - status update: {house}{unit}:{command}", house=house, unit=unit, command=command)
        unit = int(unit)
        if deviceObj is None:
            if house in self.x10_devices and unit in self.x10_devices[house]:
              deviceObj = self.x10_devices[house][unit]
            else:
                YomboWarning("X10 API received a status update, but no device object to reference it.")

        newstatus = None
        humanstatus = None
        tempcmd = command.upper()

#        self._DevicesByType('x10_appliance')
        device_type = self._DeviceTypes[deviceObj.device_type_id]
        logger.debug("self._DevicesByType('x10_appliance'): {dt}", dt=self._DeviceTypes.devices_by_device_type('x10_appliance'))
        logger.debug("device_type: {dt}", dt=device_type.label)
        if device_type.machine_label == 'x10_appliance':
            logger.debug("in x10 appliance")
            if tempcmd == 'ON':
                newstatus = 1
                humanstatus = 'On'
            elif tempcmd == 'OFF':
                newstatus = 0
                humanstatus = 'Off'
        elif device_type.machine_label == 'x10_lamp': # basic lamp
            logger.debug("in x10 lamp")
            if tempcmd == 'ON':
                newstatus = 1
                humanstatus = '100%'
            elif tempcmd == 'OFF':
                newstatus = 0
                humanstatus = 'Off'
            elif tempcmd == 'DIM':
                if type(deviceObj.status[0]['status']) is int:
                    newstatus = percentage(deviceObj.status[0]['status'] - 12 / 100)
                else:
                    newstatus = 0.88
                    humanstatus = '88%'
            elif tempcmd == 'BRIGHT':
                if type(deviceObj.status[0]['status']) is int:
                    newstatus = percentage(deviceObj.status[0]['status'] + 12 / 100)
                else:
                    newstatus = 100
                    humanstatus = '100%'

            if type(newstatus) is int:
                if newstatus > 1:
                    newstatus = 1
                    humanstatus = '100%'
                elif newstatus < 0:
                    newstatus = 0
                    humanstatus = 'Off'
            else:
                newstatus = 0
                humanstatus = 'Off'

        logger.debug("status update.  Machine: {newstatus}   Human: {humanstatus}", newstatus=newstatus, humanstatus=humanstatus)

        human_message = "%s is now %s. " % (deviceObj.area_label, humanstatus.lower())

        deviceObj.set_status(machine_status=newstatus, human_status=humanstatus, human_message=human_message,
                             source="x10api")
    
    def remove_x10_command(self, x10cmd):
        """
        Delete an old x10cmd object
        """
        logger.debug("Purging x10cmd object: {x10cmd}", x10cmd=x10cmd.request_id)
        del self.x10cmds[x10cmd.request_id]
        logger.debug("pending x10cmds: {x10cmds}", x10cmds=self.x10cmds)

