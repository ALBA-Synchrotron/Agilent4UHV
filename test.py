

s = 'sr04/vc/serial-03'
d = f.get_device(s)

data = 0x02,0x80,0x38,0x31,0x32,0x30,0x03,0x38,0x38
[d.DevSerWriteChar([t]) for t in data]

d.DevSerReadRaw()
Out[15]: '\x02\x808120   0.0E+00\x03E8'


