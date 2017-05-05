
import fandango

#data = 0x02,0x80,0x38,0x31,0x32,0x30,0x03,0x38,0x38

TRACE = False

STX = 0x02
RS232 = 0x80
READ = 0x30
WRITE = 0x31
ETX = 0x03

ACK = 0x06
NACK = 0x15
UNKNOWN = 0x32
ERROR = 0x33
OUTR = 0x34
DISABLED = 0x35

ERRORS = {0x06:'ACK',0x15:'NACK',0x32:'UNKNOWN',
          0x33:'ERROR',0x34:'OUTR',0x35:'DISABLED'}

Commands = fandango.CaselessDict({
  'HV1_ON':11,
  'HV2_ON':12,
  'HV3_ON':13,
  'HV4_ON':14,
  'Status':205,
  'ErrorCode':206,
  'Model': 319,
  
  'SerialNumber':323,
  'SerialType':504,
  'Channel':505,
  'Units':600,
  'Mode':601,
  'Protect':602,
  'FixedStep':603,
  
  'Dev1':610,
  'Power1':612,
  'Vt1':613,
  'IProt1':614,
  'SP1':615,
  
  'Dev2':620,
  'Power2':622,
  'Vt2':623,
  'IProt2':624,
  'SP2':625,

  'Dev3':630,
  'Power3':632,
  'Vt3':633,
  'IProt3':634,
  'SP3':635,

  'Dev4':640,
  'Power4':642,
  'Vt4':643,
  'IProt4':644,
  'SP4':645,
  
  'Temp1':801,
  'Temp2':802,
  'Temp3':808,
  'Temp4':809,
  
  'Ilock':803,
  'StatusSP':804,
  
  'V1':810,
  'I1':811,
  'P1':812,
  
  'V2':820,
  'I2':821,
  'P2':822,

  'V3':830,
  'I3':831,
  'P3':832,
  
  'V4':840,
  'I4':841,
  'P4':842,

  })

def str2bytes(seq):
    """ Converts an string to a list of integers """
    return map(ord,str(seq))
  
def get_crc(data,acc=0):
  '''
  XOR of all characters, ETX included but not STX.
  Return as hexadecimal code in 2 characters.
  '''
  acc,icc,xcc = data[0],'',''
  for d in data[1:]: acc = acc^d
  #xcc = acc = list(format(acc,'x').upper())
  #crc = map(ord,xcc)
  #return crc
  
  xcc = format(acc,'x').upper()
  return str2bytes(xcc)
  
  #icc = [int(v,16) for v in acc]
  #xcc = [('%x'%(i)).upper() for i in icc]
  
  #print('CRC(%s) => %s => %s => %s => %s '%(
    #data,acc,icc,xcc,crc))

def get_value(value,t=None):
  if isinstance(value,(float,int)):
    return '%06.3f'%value
  elif isinstance(value,str):
    return '%10s'%value
  else:
    return '1' if value else '0'

def pack_window_message(comm,value=None,trace=False):
  ncomm = Commands.get(comm,comm)
  if TRACE or trace:
    print('pack_window_message(%s => %s)'%(comm,ncomm))
  if isinstance(ncomm,int): 
    ncomm = '%03d'%ncomm
  data = [RS232]+str2bytes(ncomm) #list(ncomm)
  if TRACE or trace:
    print('pack_window_message(%s,%s)'%(['%x'%d for d in data],value))
  if value is not None:
    data.append(WRITE)
    try:
      if str(value) not in '01': 
        if fandango.matchCl('^[\-0-9]+$',str(value)): 
          value = '%06d'%int(value)
        else:
          value = '%10s'%('%4.1e'%float(value))
    except Exception,e: 
      print('pack_window_message(%s) failed!: %s'%(value,e))
    data.extend(str2bytes(value))
  else:
    data.append(READ)
  data.append(ETX)
  crc = get_crc(data)
  data.extend(crc)
  data.insert(0,STX)
  if TRACE or trace:
    print(['%x'%i for i in data])
  return data

def unpack_window_message(msg,trace=False):
  data = list(msg)
  if TRACE or trace:
    print('unpack_window_message(%s[%d])'%(data,len(data)))
  data.pop(0) #STX
  a = data.pop(0) #Address)
  crc,data = data[-2:],data[:-2]
  e = data.pop(-1) #ETX
  
  if len(data)>=3:
    w,data = data[:3],data[3:] #Window
    c = data.pop(0) if data else ''#Comm
  else:
    w,c = '',data.pop(0)
    assert c == ACK, '%s Error Received!'%ERRORS.get(ord(c),'Unknown')
    
  return fandango.Struct({
    'data':data,'CRC':crc,
    'command':c,'window':w,
    'address':a
    })
  
  