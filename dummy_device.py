#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 24 10:55:34 2022

@author: max
"""

import random
import threading
import re
from functools import partial

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStyleOption, QStyle, QScrollArea, QLabel
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import numpy as np

import time
from random import random as rand
from pylsl import StreamInfo, StreamOutlet, StreamInlet, local_clock, resolve_byprop
from lib import gazeReplayDevice, replayViewSetup, replay_manager
import lib

class dummyDeviceReplay(gazeReplayDevice):
    """ dummy device to test without connecting devices - replay edition"""
    def __init__(self, name, streams):
        super().__init__(name,streams)
        print(self.streams)

        self.views = {'EEG graph': { "display title:": f"{self.name} EEG graph", "wid" : partial(eeg_graph_replay, stream = self.streams[name+"_EEG"]), 
                            "stream" : self.streams[name+"_EEG"]},
              'ECG Graph': { "display title:": f"{self.name} ECG graph", "wid" : partial(ecg_graph_replay,stream = self.streams[name+"_ECG"]),
                                 "stream" : self.streams[name+'_ECG']}
              }
        if name == "Dummy_Device199":
            self.views["Scene video"] =  { "display title:": f"{self.name} front video", "wid" : partial(front_video_replay ,stream = self.streams[name+"_vid"]),
                               "stream" : self.streams[name+'_vid']}


class ecg_graph_replay( pg.widgets.PlotWidget.PlotWidget):
    def __init__(self,stream):
        super().__init__()
        replayViewSetup(self,stream)
        self.resize(500,200)
        
        #creat a curve for each channel in recording
        self.plt = self.getPlotItem()
        self.curves = [pg.PlotCurveItem(x = np.array([]),y = np.array([]), pen = (i,3), autoDownsample=True) for i in range(len(self.cols))]
        for i in range(len(self.cols)):
            self.plt.addItem(self.curves[i])
        
        #diplay labels next to channel curves
        channel_names = ["chanel 1", "channel 2", "channel 3"]
        axis_label = [[(pos + 0.5, label)] for pos,label in zip(range(1,len(channel_names)+1),channel_names)]
        self.plt.getAxis("left").setTicks( axis_label )
        
        replay_manager.time_changed.connect(self.draw_graph)
    
    def draw_graph(self, time):
        timestamps, chunk = self.pull(time-3000,time)
        for i in range(len(timestamps)):
            self.curves[i].setData(timestamps[i],chunk[i]+i)
            

class eeg_graph_replay(QScrollArea):
    def __init__(self,stream, excluded_channels = []):
        super().__init__()
        self.setWidgetResizable(True) 
        self.resize(500,600)
        
        self.pw = pg.plot()
        self.plt = self.pw.getPlotItem()
        self.setWidget(self.pw)  
        
        #get stream infos from the stream name passed
        stream_info = resolve_byprop('name',stream["lsl name"],timeout = 1)[0]
        channel_names = stream["channel names"]
        
        #exclude channel containing excluded words
        print("channel names", channel_names)
        self.excluded_idx = [ i for i in range(len(channel_names)) if [word for word in excluded_channels if word in channel_names[i]] ]
        print("exculed idx",self.excluded_idx)
                           
                           
        inlet = StreamInlet(stream_info)
        channel_count = stream_info.channel_count()
        sampling_rate = stream_info.nominal_srate()
            
        #create the plot lines, one per channel on the stream
        self.curves = [pg.PlotCurveItem(x = np.array([]),y = np.array([]), pen = (i,len(channel_names)), autoDownsample=True)
                       for i in range(channel_count) if i not in self.excluded_idx]
        print("number of curves",len(self.curves))
        for curve in self.curves:
            self.plt.addItem(curve)
           
        eeg_channel_names = [name for name in stream["channel names"] if not [word for word in excluded_channels if word in name]]
        #made this way to conform to the retarded format of pyqtgraph.AxisItem.setTicks
        axis_label = [[(pos , label) for pos,label in zip(range(1,len(eeg_channel_names)+1),eeg_channel_names)],[]] 
        self.plt.getAxis("left").setTicks( axis_label )
        
        #starts the thread tha will read from lsl, add the data to the lines and refresh the view
        self.reader_thread = threading.Thread(name = "eeg_graph_reader_thread"+stream["lsl name"],
                                              target = self.graph_eeg, args = [inlet,channel_count,sampling_rate], daemon=True)
        self.reader_thread.start()   
    def graph_eeg(self, inlet, channel_count, sampling_rate, refresh_rate = 15):
        y = np.array([[]]*len(self.curves))
        x = np.array([])
        while True:
            chunk, timestamps = inlet.pull_chunk()

            if timestamps:
                chunk, timestamps = np.array(chunk), np.array(timestamps)                
                #print("chunk and ts shapes", chunk.shape, timestamps.shape)
                chunk = np.delete(chunk,self.excluded_idx,axis = 1)
                #print("chunk and ts shapes after exclusion", chunk.shape, timestamps.shape)
                chunk = chunk.transpose()
                x = np.append(x,timestamps)
                y = np.append(y,chunk,axis = 1)
                for i in range(len(self.curves)):
                    #self.curves[i].setData(x,y[i]+i-1)
                    self.curves[i].setData(x,y[i]/np.mean(y[i,-1000:])+i)
                
                #purge plot data that are too old
                max_saved = int(sampling_rate * 30)
                if x.shape[0] > max_saved:
                    x = x[-max_saved:]
                    y = y[:,-max_saved:]
                #adjust the view to the 15 last seconds counting from the time of the last timestamp
                self.pw.setXRange(timestamps[-1]-5, timestamps[-1])
            time.sleep(1/refresh_rate) #set refresh rate            
        
class front_video_replay(QWidget):
    def __init__(self,stream):
        super().__init__()
        replayViewSetup(self, stream)
        
        #initialize video box
        self.vidContainer = QLabel("",self)
        self.pixmap = QPixmap(640,480)
        self.pixmap.fill(QColor("black"))
        self.vidContainer.setPixmap(self.pixmap)
        
        #connect to corresponding frameVideo
        replay_manager.time_changed.connect(self.draw_frame)
        
    def draw_frame(self, time):
        ts, chunk = self.pull(time)
        print(ts,chunk)
        
        
lib.supported_devices.append(dummyDeviceReplay)       

