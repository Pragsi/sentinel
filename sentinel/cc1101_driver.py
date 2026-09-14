import spidev, time

PARTNUM=0x30
VERSION=0x31
RSSI=0x34

SRES=0x30
SIDLE=0x36
SCAL=0x33
SRX=0x34
STX=0x35
SFTX=0x3B

FREQ2=0x0D
FREQ1=0x0E
FREQ0=0x0F
MDMCFG4=0x10
MDMCFG3=0x11
MDMCFG2=0x12
MDMCFG1=0x13
MDMCFG0=0x14
DEVIATN=0x15
PKTCTRL0=0x08
PKTLEN=0x06
IOCFG0=0x02
IOCFG2=0x00
FREND0=0x22
PATABLE=0x3E
TXFIFO=0x3F

class CC1101:
    def __init__(self, bus=0, cs=0):
        self.spi=spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz=500000
        self.spi.mode=0

    def close(self):
        try: self.spi.close()
        except: pass

    def strobe(self,cmd):
        return self.spi.xfer2([cmd])[0]

    def write(self,addr,val):
        self.spi.xfer2([addr & 0x3F,val & 0xFF])

    def write_burst(self,addr,data):
        self.spi.xfer2([addr | 0x40] + list(data))

    def status(self,addr):
        return self.spi.xfer2([addr | 0xC0,0])[1]

    def detect(self):
        p=self.status(PARTNUM)
        v=self.status(VERSION)
        return p,v,(p==0x00 and v not in (0x00,0xFF))

    def set_freq(self,mhz):
        word=int((mhz*1_000_000/26_000_000)*(1<<16))
        self.write(FREQ2,(word>>16)&0xFF)
        self.write(FREQ1,(word>>8)&0xFF)
        self.write(FREQ0,word&0xFF)

    def configure_ook_rx(self,mhz=433.92):
        self.strobe(SIDLE)
        self.strobe(SRES)
        time.sleep(0.01)
        self.set_freq(mhz)
        self.write(MDMCFG4,0xF6)
        self.write(MDMCFG3,0x83)
        self.write(MDMCFG2,0x30)
        self.write(MDMCFG1,0x22)
        self.write(MDMCFG0,0xF8)
        self.write(DEVIATN,0x15)
        self.write(PKTCTRL0,0x32)
        self.write(IOCFG0,0x0D)
        self.write(IOCFG2,0x0E)
        self.strobe(SCAL)
        time.sleep(0.01)
        self.strobe(SRX)

    def rssi_dbm(self):
        raw=self.status(RSSI)
        if raw>=128:
            raw-=256
        return raw/2.0 - 74.0

    def lab_tx_burst(self,mhz=433.92,repeats=3):
        self.strobe(SIDLE)
        self.strobe(SRES)
        time.sleep(0.01)
        self.set_freq(mhz)
        self.write(MDMCFG4,0xF6)
        self.write(MDMCFG3,0x83)
        self.write(MDMCFG2,0x30)
        self.write(MDMCFG1,0x22)
        self.write(MDMCFG0,0xF8)
        self.write(PKTCTRL0,0x00)
        self.write(FREND0,0x11)
        self.write_burst(PATABLE,[0x60])
        pattern=bytes([0xAA,0x55,0xAA,0x55,0x0F,0xF0,0x33,0xCC])
        self.write(PKTLEN,len(pattern))
        for _ in range(repeats):
            self.strobe(SFTX)
            self.write_burst(TXFIFO,pattern)
            self.strobe(STX)
            time.sleep(0.15)
            self.strobe(SIDLE)
            time.sleep(0.25)
