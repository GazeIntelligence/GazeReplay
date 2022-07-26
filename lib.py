
import sys, os
sys.path.append(os.path.dirname(__file__))
from functools import partialmethod, partial
import json

from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QObject, QTime, QTimer
from PyQt5.QtWidgets import QApplication
import pandas as pd
import numpy as np



class replayManager(QObject):   
    config = {}
    df : pd.DataFrame
    time_changed = Signal(int)
    def __init__(self, path = 'test_recording'):
        super().__init__()
        self.df = pd.read_csv(f"{path}/recordings.csv", index_col=0)
        self.df.index = self.df.index - np.min(self.df.index) 
        self.df.index = (np.array(self.df.index) * 1000).astype(int)
        self.df.sort_index()
        print(self.df)
        self.time_range = (self.df.index[0], self.df.index[-1])
        with open(f"{path}/stream_config.json") as f:
            self.config['streams'] = json.load(f)
            
        self.time = 0
        self.step = 100
            
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick_time)
        
        
    def tick_time(self, ):
        if self.time < self.time_range[1]-self.step:
            self.time = self.time+self.step
            self.on_time_changed(self.time)
    def on_time_changed(self,time):
        self.time = time
        self.time_changed.emit(time)

replay_manager = replayManager()
        
supported_devices = []
active_devices = []  

autorecord = True


#not made as a class because of multiple inheritance problems but acts as a constructor
def replayViewSetup(caller, stream, timeframe = 0): 
    caller.df = replay_manager.df
    caller.cols = stream["full channel names"]
    
    def pull(self, start_time, end_time = None ):
        start_idx = np.searchsorted(self.df.index,start_time)
        if end_time:
            end_idx = np.searchsorted(self.df.index, end_time)
        else:
            end_idx = start_idx

        print("===times==",start_time,self.df.index[start_idx],end_time,self.df.index[end_idx])
        d = self.df.iloc[start_idx:end_idx][self.cols]
        raw_ts, raw_chunk = d.index.to_numpy(), d.to_numpy().transpose()
        
        ts, chunks = [], []
        
        for chunk in raw_chunk:
            mask = np.where(~np.isnan(chunk))
            ts.append(raw_ts[mask])
            chunks.append(chunk[mask])

        return ts, chunks
    caller.pull = pull.__get__(caller)

class gazeReplayDevice(QObject):
    """ base calss of the replay devices"""
    def __init__(self,name,streams):
        super().__init__()
        self.name = name 
        self.streams = { s["lsl name"] : s for s in streams}
        
def partialclass(cls, *args, **kwds):
    class NewCls(cls):
        __init__ = partialmethod(cls.__init__, *args, **kwds)
    return NewCls

def getMainWindow():
    # Global function to find the (open) QMainWindow in application
    app = QApplication.instance()
    for widget in app.topLevelWidgets():
        if hasattr(widget,'isMainWindow'):
            return widget
    return None



class global_signals(QObject):
    """ global signals class"""
    found_device = Signal(object)  
sig = global_signals()




def filter_dict(k,v,d):
    return [x for x in d if x[d] == v]


def make_stream(**kwargs):
    stream = {"display tile":None, "active": True, "type": "lsl", "lsl name": None, "channel names" : [], "device": None}
    for k,v in kwargs.items():
        k = k.replace('_',' ')
        stream[k] = v
    return stream

    
