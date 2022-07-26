# -*- coding: utf-8 -*-

import re
from functools import partial
import threading
import time

from pylsl import resolve_streams, StreamInlet, resolve_byprop
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QScrollArea, QWidget

from lib import supported_devices
from dummy_device import eeg_graph as eeg_graph2


class smartingEEG():
    streams : dict
    views : dict
    name : str
    
    def discover(timeout = 7):
        print("Scanning for Smarting Mobi devices..")
        lsl_streams = resolve_streams(timeout)
        found_streams = [x for x in lsl_streams if "Android_EEG" in x.name()]
        print("found the following smarting eeg devices :", [x.name() for x in found_streams])
        return [ smartingEEG(stream_info) for stream_info in found_streams]
    def __init__(self, stream_info):
        self.name = "Smarting Mobi " + stream_info.name().split('_')[-1]
        
        self.streams = {"all streams": {'display title': "All streams", "name": "all_streams", 
                                   "channel names": [], "type": "lsl", "lsl name": stream_info.name(), "active": True, "device": self},
                   }
        self.info = StreamInlet(stream_info).info().as_xml()
        self.streams["all streams"]["channel names"] = [ x[7:-8] for x in re.findall(r'<label>.*</label>',self.info)]
        
        self.views = {"EEG Graph" : { "wid" : partial(eeg_graph_smarting, stream = self.streams["all streams"], excluded_channels = ["Gyro","Acc","GPS"]),
                                       "display title": f"{self.name} EEG Graph", "stream":self.streams["all streams"]}
                        }
    def stream_lsl(self):
        pass
    

class eeg_graph(QScrollArea):
    def __init__(self,stream_name):
        super().__init__()
        self.setWidgetResizable(True) 
        self.resize(500,600)
        
        self.pw = pg.plot()
        self.plt = self.pw.getPlotItem()
        self.setWidget(self.pw)  
        
        #get stream infos from the stream name passed
        stream_info = resolve_byprop('name',stream_name,timeout = 1)[0]
        inlet = StreamInlet(stream_info)
        channel_count = stream_info.channel_count()
        sampling_rate = stream_info.nominal_srate()
            
        #create the plot lines, one per channel on the stream
        self.curves = [pg.PlotCurveItem(x = np.array([]),y = np.array([]), pen = (i,3), autoDownsample=True) for i in range(channel_count)]
        for i in range(channel_count):
            self.plt.addItem(self.curves[i])
            
        eeg_channel_names = stream["ch"]
        axis_label = [[(pos - 0.5, label)] for pos,label in zip(range(1,len(eeg_channel_names)+1),eeg_channel_names)]
        self.plt.getAxis("left").setTicks( axis_label )
        
        #starts the thread tha will read from lsl, add the data to the lines and refresh the view
        self.reader_thread = threading.Thread(name = "ecg_graph_reader_thread"+stream_name,
                                              target = self.graph_ecg, args = [inlet,channel_count,sampling_rate], daemon=True)
        self.reader_thread.start()
    
    def graph_eeg(self, inlet, channel_count, sampling_rate, refresh_rate = 30):
        y = np.array([[]]*len(self.curves))
        x = np.array([])
        while True:
            chunk, timestamps = inlet.pull_chunk()
            chunk = np.array(chunk).transpose()
            if timestamps:
                x = np.append(x,timestamps)
                y = np.append(y,chunk,axis = 1)
                for i in range(channel_count):
                    self.curves[i].setData(x,y[i]+i-1)
                
                #purge plot data that are too old
                max_saved = int(sampling_rate * 90)
                if x.shape[0] > max_saved:
                    x = x[-max_saved:]
                    y = y[:,-max_saved:]
                #adjust the view to the 10 last seconds counting from the time of the last timestamp
                self.pw.setXRange(timestamps[-1]-10, timestamps[-1])
            time.sleep(1/refresh_rate) #set refresh rate
            
class eeg_graph_smarting(eeg_graph2):
    pass
            
supported_devices.append(smartingEEG)