

import sys,traceback,time,re
import fandango
import PyTango
import windowprotocol as WP

from fandango import Dev4Tango
from fandango.functional import *
from fandango.threads import wait
from fandango.dicts import ThreadDict
from PyTango import Device_4Impl,DevState,DevFailed,DeviceClass,DeviceProxy

def catched(f):
  def wrapper(*args,**kwargs):
    try:
      return f(*args,**kwargs)
    except:
      traceback.print_exc()
  return wrapper

class Agilent4UHV(Dev4Tango):
  
  def __init__(self,cl,name):
    self.call__init__(Dev4Tango,cl,name)
    self.lg=fandango.Logger('test')
    self.init_device()
    
  def delete_device(self):
    try:
      self.thread.stop()
    except:
      traceback.print_exc()
    
  def init_device(self):
    self.lg.info("init_device()")
    self.get_device_properties(self.get_device_class())
    self.info('LogLevel = %s'%self.getLogLevel())
    self.set_state(DevState.ON)
    self.last_comm = 0
    self.exception = ''
    self.serial = DeviceProxy(self.SerialLine)
    self.thread = ThreadDict(
      read_method = self.send_command,
      write_method = self.send_command,
      timewait = self.TimeWait,
      )
    
    self.dyn_attr()
    self.thread.start()
    self.info("Ready to accept request ...")
    self.info('-'*80)
    
  @catched
  def dyn_attr(self):
    self.dyn_attrs = getattr(self,'dyn_attrs',[])
    self.info('dyn_attr(%s)'%self.dyn_attrs)
    for l,n in product('VPI','1234'):

      if l+n not in self.dyn_attrs:
        self.info('Adding attribute: %s'%(l+n))
        unit,frmt = {'V':('V','%d'),'P':('mbar','%g'),'I':('mA','%g')}[l]
        attrib = PyTango.Attr(l+n,PyTango.DevDouble, PyTango.AttrWriteType.READ)
        props = PyTango.UserDefaultAttrProp()
        props.set_format(frmt),props.set_unit(unit)
        attrib.set_default_properties(props)
        self.add_attribute(attrib,self.read_dyn_attr,None,self.is_Attr_allowed)
        
      self.thread.append(l+n,period=self.Refresh)
      
    for a in ('Model','ErrorCode'):
      self.info('Adding attribute: %s'%(a))
      attrib = PyTango.Attr(a,PyTango.DevString, PyTango.AttrWriteType.READ)
      self.add_attribute(attrib,self.read_dyn_attr,None,self.is_Attr_allowed)
      self.thread.append(a,period=self.Refresh*5)
  
  def always_executed_hook(self):
    self.state_machine()
    
  #############################################################################
  
  #@catched
  def send_command(self,comm,value=None,throw=False):
    r,s = '',''
    try:
      data = WP.pack_window_message(comm,value)
      (self.info if throw else self.debug)(
        'send_command(%s,%s) => %s'%(comm,value,data))
      [self.serial.DevSerWriteChar([t]) for t in data]
      wait(self.TimeWait)
      r = self.serial.DevSerReadRaw()
      assert r, 'NothingReceived!'
      self.last_comm = now()
      self.exception = ''
    except Exception, e:
      self.error('send_command(%s):\n %s'%(comm,traceback.format_exc()))
      self.exception = str(e)
      if throw:
        raise e
        #PyTango.Except.throw_exception("Agilent4UHV Exception",str(e),str(e))
      return r

    try:
        s = WP.unpack_window_message(r).data
        s = ''.join(s) if isSequence(map(str,s)) else str(s)
    except Exception,e:
        traceback.print_exc()
        raise e
    return s
    
  @catched
  def state_machine(self):
    try:
      if self.last_comm < now()-60 or not all(self.thread.values()):
        if self.get_state() != DevState.INIT:
          self.set_state(DevState.UNKNOWN)
      else:
        self.set_state(DevState.ON)
      status = self.default_status()
      status += '\nLast communication was at %s'%(time2str(self.last_comm))
      status += '\n'
      if self.exception:
        status += '\nLast error was %s\n\n'%(self.exception[:80])
      for k,v in sorted(self.thread.items()):
        status += '\n%s:%s'%(k,v)
      self.set_status(status)
    except:
      self.error(traceback.format_exc())
      
  def is_Attr_allowed(self,*args):
    self.debug('In is_Attr_allowed(%s)'%str(args))
    return True
  
  def read_dyn_attr(self,attr):
    attrname = attr.get_name().upper()
    self.info('In read_dyn_attr(%s)'%attrname)
    try:
      if not self.thread.get(attrname):
        # If it's the first reading, force a hardware update
        try:
          alive = self.thread.alive()
          alive and self.thread.stop()      
          self.thread.__getitem__(attrname,hw=True)
          self.thread._updates[attrname] = time.time()
        except Exception,e:
          traceback.print_exc()
          raise e
        finally:
          alive and self.thread.start()

      # Read last cached value
      v = self.thread[attrname]
      self.debug('%s: %s'%(attrname,v))
      try:
        attr.set_value(float(v))
      except:
        attr.set_value(v)
    except Exception,e:
      traceback.print_exc()
      raise e
    
  def read_LastUpdate(self,attr):
    attr.set_value(self.thread.get_last_update())
    
  ##############################################################################
  # Public Methods
  
  def SendCommand(self,argin,throw=True):
    """
    Argin can be "command", ("command","value") 
    or a sequence of [(c,v)] pairs
    """
    s,argin = '',toSequence(argin)
    if not isSequence(argin[0]): argin = [argin]
    try:
      self.Pause()
      WP.TRACE = True
      for arr in argin:
        comm,value = arr[0],(arr[1:] or (None,))[0]
        s = self.send_command(comm,value,throw=throw)
        self.info('SendCommand(%s) <= %s'%(argin,s))
        
      return s
    except Exception,e:
      traceback.print_exc()
      if throw: 
        print('!'*80)
        raise e
    finally:
      WP.TRACE = False
      self.Resume()
      
  #def SendDualCommand(self,argin=None):
    #""" Send commands using the old Dual protocol
    #"""
    #msg = [0x81,2+1+0,ord('Z'),ord('0'),0x30,]
    #crc = 0x7f
    #for d in msg: crc = crc^d
    #msg.append(crc)
    #print(msg)
    #self.Pause()
    #[self.serial.DevSerWriteChar([t]) for t in data]
    #wait(self.TimeWait)
    #r = self.serial.DevSerReadRaw()
    #self.Resume()

  def SetMode(self,argin):
    assert argin in ('SERIAL','LOCAL','REMOTE'),'WrongMode!'
      
  def Pause(self,alive=False):
    alive = alive or self.thread.alive() 
    if alive: self.thread.stop()
    return alive
    
  def Resume(self,alive=False):
    alive = alive or self.thread.alive()
    if not alive: self.thread.start()
    return alive
    
  def On(self):
    return self.SendCommand()
    
  def OnHV1(self):
    return str(self.SendCommand(('HV1_ON',1),throw=True))

  def OnHV2(self):
    return str(self.SendCommand(('HV2_ON',1),throw=True))
    
  def OnHV3(self):
    return str(self.SendCommand(('HV3_ON',1),throw=True))

  def OnHV4(self):
    return str(self.SendCommand(('HV4_ON',1),throw=True))
    
  def Off(self):
    return self.SendCommand()
    
  def OffHV1(self):
    return str(self.SendCommand(('HV1_ON',0),throw=True))

  def OffHV2(self):
    return str(self.SendCommand(('HV2_ON',0),throw=True))

  def OffHV3(self):
    return str(self.SendCommand(('HV3_ON',0),throw=True))
    
  def OffHV4(self):
    return str(self.SendCommand(('HV4_ON',0),throw=True))

  
class Agilent4UHVClass(DeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'SerialLine':
            [PyTango.DevString,
            "SerialLine Device Server to connect with",
            [''] ],
        'Refresh':
            [PyTango.DevDouble,
            "Period (in seconds) for the internal refresh thread (1 entire cycle).",
            [ 3.0 ] ],
        'TimeWait':
            [PyTango.DevDouble,
            "Period (in seconds) to wait for device answer.",
            [ 0.2 ] ],  
        'LogLevel':
            [PyTango.DevString,
            "",
            [ 'INFO' ] ],
        'DefaultStatus':
            [PyTango.DevString,
             "On/Off,On/Off; the expected status for each channel, empty if not used",
             ['']],
            }            
            
    #    Command definitions
    cmd_list = {
        'SendCommand':
            [[PyTango.DevVarStringArray, "Command to send (literally)"],
             [PyTango.DevString,
                "Answer received to command sended (literally)"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'SetMode':
            [[PyTango.DevString, "Mode to set (LOCAL/SERIAL/REMOTE)"],
             [PyTango.DevString,
                "Mode to set"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'Pause': [[PyTango.DevVoid, ""],[PyTango.DevVoid,""]],
        'Resume':
          [[PyTango.DevVoid, ""],[PyTango.DevVoid,""]],
        'On':
            [[PyTango.DevShort, "With 0, switches On all High voltage channels"
              " (managed by DefaultStatus)"],
             [PyTango.DevString,
                "With 0, switches On all High voltage channels"
              " (managed by DefaultStatus)"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'Off':
            [[PyTango.DevShort, "With 0, switchs Off all High voltage channels"
              " (managed by DefaultStatus)"],
             [PyTango.DevString,
                "With 0, switches On all High voltage channels"
              " (managed by DefaultStatus)"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OnHV1':
            [[PyTango.DevVoid, "Switchs On the High voltage channel"],
             [PyTango.DevString, "Switchs On the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OffHV1':
            [[PyTango.DevVoid, "Switchs Off the High voltage channel"],
             [PyTango.DevString, "Switchs Off the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OnHV2':
            [[PyTango.DevVoid, "Switchs On the High voltage channel"],
             [PyTango.DevString, "Switchs On the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OffHV2':
            [[PyTango.DevVoid, "Switchs Off the High voltage channel"],
             [PyTango.DevString, "Switchs Off the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OnHV3':
            [[PyTango.DevVoid, "Switchs On the High voltage channel"],
             [PyTango.DevString, "Switchs On the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OffHV3':
            [[PyTango.DevVoid, "Switchs Off the High voltage channel"],
             [PyTango.DevString, "Switchs Off the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OnHV4':
            [[PyTango.DevVoid, "Switchs On the High voltage channel"],
             [PyTango.DevString, "Switchs On the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
        'OffHV4':
            [[PyTango.DevVoid, "Switchs Off the High voltage channel"],
             [PyTango.DevString, "Switchs Off the High voltage channel"],
             {
                'Display level': PyTango.DispLevel.EXPERT,
            }],
          }
             
    attr_list = dict(getattr(Dev4Tango,'attr_list',{}))
             
    @staticmethod
    def get_default_attr(name='',unit='',format='%5.2e'):
      return [[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ],
        {'unit': "mA",'format': "%5.2e",'description':name}]

##############################################################################
        
def main(args):
    try:
        fandango.log.info('Agilent4UHV.main(%s)'%args)
        py = PyTango.Util(args)
        py.add_TgClass(Agilent4UHVClass, Agilent4UHV, 'Agilent4UHV')

        U = PyTango.Util.instance()
        U.server_init()
        fandango.log.info('Agilent4UHV.server_run()')
        U.server_run()

    except PyTango.DevFailed, e:
        print('-------> Received a DevFailed exception:', e)
    except Exception, e:
        print('-------> An unforeseen exception occured....', e)
  
if __name__ == '__main__':
  import sys
  main(sys.argv)
             
