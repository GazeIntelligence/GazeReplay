import threading
from functools import partial, partialmethod

import bluetooth
from pylsl import resolve_byprop, StreamInlet

from . import libfaros
from lib import supported_devices, partialclass

class farosDevice():
    device_type = 'faros'
    name: str
    widgets = {}
    streams = {'lsl':{'ECG':'ECG', 'Accélleromètre':'acc', 'hardware markers':'marker', "Pics RR":'RR', 'Température':'temp'},
               'other': {}
               }
    
    active_streams = {'lsl': [], 'other' : []}
    
    mac = ''
    socket = None
    streamer_thread = None
    
    def discover(timeout = 7):
        threading.current_thread().name = "faros-discovery"
        print("scanning for Faros devices")
        nearby_devices = bluetooth.discover_devices(timeout)
        found_devices = []
        for bdaddr in nearby_devices:
            name = bluetooth.lookup_name(bdaddr)
            if name and 'FAROS' in name:
                found_devices.append(farosDevice(bdaddr,name))
        print("Found the following Faros devices:",[x.name for x in found_devices])
            
        return found_devices 
    
    def __init__(self, mac,name):
        self.mac = mac
        self.name = name
        self._connect()
        
        self.properties  = libfaros.get_properties(self.socket)
        self.settings  = libfaros.unpack_settings(self.properties['settings'])
        
        self.active_streams['lsl'] = list(self.streams['lsl'].values())
        self.active_streams['other'] = list(self.streams['other'].values())
        
        self.widgets = {'ECG graph': partialclass(ecg_graph,self.name+'_ECG')}
    
    def _connect(self):
        """ Connect to a device using the bluetooth address addr. """
        addr = self.mac
        port = 1 
        
        #if its a second gen device get the right port for it
        services = bluetooth.find_service(address = addr)       
        for serv in services:
            if serv["name"] == b'Bluetooth Serial Port' or serv["name"] == 'Bluetooth Serial Port' :
                port = serv["port"]  
    	    
        self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        print(f"connecting to port {port} of {self.name} with address {addr}")
        self.socket.connect((addr, port))
        command = "wbaoms"
        res = libfaros.send_command(self.socket, command, 7)
        print(self.name,":  connection finished")
          
    def stream_lsl(self):
        if self.streamer_thread:
            self.streamer_thread.stop()
            del self.streamer_thread
        print('active streams from device',self.active_streams)
        if self.active_streams['lsl']:
            self.streamer_thread = libfaros.stream_lsl(self.socket,self.active_streams['lsl'],self.settings, self.name)
            self.streamer_thread.start()
        
        
supported_devices.append(farosDevice)

import numpy as np   
import pyqtgraph as pg
import time

class ecg_graph(pg.widgets.PlotWidget.PlotWidget):
    def __init__(self,stream_name):
        super().__init__()
        self.resize(500,200)
        
        #setup plot widget with stream name as title   
        self.plt = self.getPlotItem()
        self.plt.enableAutoRange(x=True,y=True)
        
        
        #get stream infos from the stream name passed
        stream_info = resolve_byprop('name',stream_name,timeout = 1)[0]
        if stream_info:
            inlet = StreamInlet(stream_info)
            channel_count = stream_info.channel_count()
            sampling_rate = stream_info.nominal_srate()
            
        #create the plot lines, one per channel on the stream
        self.curves = [pg.PlotCurveItem(x = np.array([]),y = np.array([]), pen = (i,3), autoDownsample=True) for i in range(channel_count)]
        for i in range(channel_count):
            self.plt.addItem(self.curves[i])
        
        #starts the thread tha will read from lsl, add the data to the lines and refresh the view
        self.reader_thread = threading.Thread(name = "ecg_graph_reader_thread"+stream_name,
                                              target = self.graph_ecg, args = [inlet,channel_count,sampling_rate], daemon=True)
        self.reader_thread.start()
    
    def graph_ecg(self, inlet, channel_count, sampling_rate, refresh_rate = 20):
        y = np.array([[]]*channel_count)
        x = np.array([])
        while True:
            chunk, timestamps = inlet.pull_chunk()
            chunk = np.array(chunk).transpose()
            if timestamps:
                x = np.append(x,timestamps)
                y = np.append(y,chunk,axis = 1)
                for i in range(channel_count):
                    self.curves[i].setData(x,y[i])
                
                #purge plot data that are too old
                max_saved = int(sampling_rate * 90)
                if x.shape[0] > max_saved:
                    x = x[-max_saved:]
                    y = y[:,-max_saved:]
                #adjust the view to the 10 last seconds counting from the time of the last timestamp
                old_xrange = self.getAxis("bottom").range
                #print("old x range",old_xrange)
                #print("last timestamp", timestamps[-1])
                offset =  timestamps[-1] - old_xrange[-1] 
                #print(offset)
                for i in range(1,10):
                    self.setXRange(-10 + old_xrange[-1] + (offset/10)*i, old_xrange[-1] + (offset/10)*i)                    
                    time.sleep(1/refresh_rate) 
