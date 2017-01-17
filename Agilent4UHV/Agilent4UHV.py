

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
  
  @catched
  def send_command(self,comm,value=None):
    r,s = '',''
    try:
      data = WP.pack_window_message(comm,value)
      self.debug('send_command(%s,%s) => %s'%(comm,value,data))
      [self.serial.DevSerWriteChar([t]) for t in data]
      wait(self.TimeWait)
      r = self.serial.DevSerReadRaw()
      assert r, 'NothingReceived!'
      self.last_comm = now()
      self.exception = ''
    except Exception, e:
      self.error('send_command(%s):\n %s'%(comm,traceback.format_exc()))
      self.exception = str(e)
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
      for k,v in self.thread.items():
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
  
  def SendCommand(self,argin):
    s,argin = '',toSequence(argin)
    comm,value = argin[0],(argin[1:] or (None,))[0]
    try:
      alive = self.thread.alive()
      alive and self.thread.stop()
      s = self.send_command(comm,value)
      self.info('SendCommand(%s) <= %s'%(argin,s))
      return s
    finally:
      alive and self.thread.start()
      
  def Pause(self):
    self.thread.stop()
    
  def Resume(self):
    self.thread.start()
  
  
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
          'Pause': [[PyTango.DevVoid, ""],[PyTango.DevVoid,""]],
          'Resume': [[PyTango.DevVoid, ""],[PyTango.DevVoid,""]],
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
             