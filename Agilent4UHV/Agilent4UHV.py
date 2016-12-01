

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
    self.set_state(DevState.INIT)
    self.last_comm = 0
    self.exception = ''
    self.serial = DeviceProxy(self.SerialLine)
    self.thread = ThreadDict(
      read_method = self.send_command,
      write_method = self.send_command,
      timewait = self.TimeWait,
      )
 
    ### Creating Dynamic Attributes
    #for i in range(self.NChannels):
        ##for key,values,unit,format in (('P','pressures','mbar','%1.2e'),('V','voltages','kV','%1.2f'),('I','currents','mA','%1.2e')):
        #for key,values,unit,format in (('P','pressures','mbar','%1.2e'),('I','currents','A','%1.2e')):
            #attrname = '%s%d'%(key,(i+1))
            #attrib = PyTango.Attr(attrname,PyTango.DevDouble, PyTango.AttrWriteType.READ)
            #props = PyTango.UserDefaultAttrProp(); props.set_format(format); props.set_unit(unit)
            #attrib.set_default_properties(props)
            #self.attribs[attrname] = (i,values)
            ##fun = (lambda self,attr,index=i,value=values: attr.set_value(index<self.NChannels and float(getattr(self,value)[index]) or 0.0))
            #self.log.info('Creating attribute %s ...'%attrib)
            #self.add_attribute(attrib,self.read_dyn_attr,None,self.is_dyn_allowed)
    
    self.dyn_attr()
    
    #self.thread.start()
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
  
  def always_executed_hook(self):
    self.state_machine()
    
  #############################################################################
  
  @catched
  def send_command(self,comm,value=None):
    try:
      data = WP.pack_window_message(comm,value)
      self.debug('send_command(%s,%s) => %s'%(comm,value,data))
      [self.serial.DevSerWriteChar([t]) for t in data]
      wait(self.TimeWait)
      r = self.serial.DevSerReadRaw()
      assert r, 'NothingReceived!'
      self.last_comm = now()
      self.exception = ''
      return r
    except Exception, e:
      self.error('send_command(%s):\n %s'%(comm,traceback.format_exc()))
      #print getLastException()
      self.exception = str(e)
      #PyTango.Except.throw_exception("Agilent4UHV Exception",str(e),str(e))
      return ''
    
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
  
  def read_dyn_attr(self,attr):
    attrname = attr.get_name().upper()
    self.debug('In read_dyn_attr(%s)'%attrname)
    attr.set_value(float(self.thread[attrname]))
    
    
    #index,value = self.attribs[attrname]
    #value = index<self.NChannels and float(getattr(self,value,[0.]*(index+1))[index] or 0.0)
    #if not self.read_CableEnabled()[index] and any(v>0.0 for v in (self.voltages[index],self.currents[index],self.pressures[index])): 
        #quality = PyTango.AttrQuality.ATTR_ALARM
    #else: quality = PyTango.AttrQuality.ATTR_VALID
    #attr.set_value_date_quality(value,time.time(),quality)
  
  def SendCommand(self,argin):
    argin = toSequence(argin)
    comm,value = argin[0],(argin[1:] or (None,))[0]
    try:
      alive = self.thread.alive()
      alive and self.thread.stop()
      r = self.send_command(comm,value)
      self.info('SendCommand(%s) <= %s'%(argin,r))
      return r
    finally:
      alive and self.thread.start()
  
  
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
          }
             
    @staticmethod
    def get_default_attr(name='',unit='',format='%5.2e'):
      return [[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ],
        {'unit': "mA",'format': "%5.2e",'description':name}]

    #attr_list = dict(
      #[a for i in '1234' for a in [
        #('V'+i,get_default_attr('V'+i,'V','%5d')),
        #('P'+i,get_default_attr('P'+i,'mbar','%5.2e')),
        #('I'+i,get_default_attr('I'+i,'mA','%5.2e'))
        #])

    #def __init__(self, name):
        #PyTango.DeviceClass.__init__(self, name)
        #self.set_type(name)
        #print "In Agilent4UHVClass  constructor"
        
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
        print '-------> Received a DevFailed exception:', e
    except Exception, e:
        print '-------> An unforeseen exception occured....', e  
  
if __name__ == '__main__':
  import sys
  main(sys.argv)
             