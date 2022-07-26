import sys, os
import asyncio
import threading
import time
import subprocess as sp

from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QObject
import numpy as np
import shlex


sys.path.append(os.path.dirname(__file__))
from pupil_labs.realtime_api.simple import discover_devices, discover_one_device, Device
from pupil_labs.realtime_api.models import DiscoveredDeviceInfo
from invisible_lsl_relay import cli
from lib import supported_devices, partialclass, stream_recorder



class piDevice():
    device_type = "pupil_invisible"
    name: str
    widgets = {}
    streams = { "lsl": {"Gaze Position" : "Gaze"},
                "other": {"Vidéo Frontale" : None}
                }
    active_streams = {'lsl': [], 'other': []}
    
    dev : Device
    info : DiscoveredDeviceInfo
    streaming_thread = None
    
    def discover(timeout = 7):
        test = True #to skip search for additional devices when testing
        print("scanning for Pupil-invisible devices")
        threading.current_thread().name = "pupil-invisible-discovery"
        if test:
            devices = []
        else:
            devices = discover_devices(timeout)
        try:
            local_dev = Device('pi.local',8080)
            print(local_dev)
            if local_dev.phone_id not in [dev.phone_id for dev in devices]:
                devices.append(local_dev)
        except OSError:
            print("couldn't find Pupil invisible device on pi.local")
        devices = [ piDevice(d) for d in devices ]
        print("Found the following Pupil invisible devices:", [x.name for x in devices])
        return devices
    
    def __init__(self,dev):
        
        full_name = f"PI monitor:{dev.phone_name}:{dev.phone_id}.http._tcp.local."
        self.dev = dev
        self.info = DiscoveredDeviceInfo(name = full_name, server = dev.dns_name, port = dev.port ,addresses = [dev.phone_ip])
        self.name = f'Pupil-invisible{self.dev.phone_id}'
        
        for k,v in self.streams['lsl'].items():
            self.streams['lsl'][k] = f"pupil_invisible_{self.info.addresses[0]}_{v}"
        self.active_streams["lsl"] = list(self.streams["lsl"].values())
        
        self.streams["other"]["Vidéo Frontale"] = frontVideo(dev, self.name+'_front_video')
        
        self.widgets = { "frontal video with gaze v2": partialclass(videoWidget2, pi_device = self) }
        
        
    def stream_lsl(self):
        if self.streaming_thread:
            del self.streaming_thread
        if self.active_streams['lsl']: #if there are active lsl streams   
            self.streaming_thread = threading.Thread(target = self._start_lsl_relay)
            self.streaming_thread.start()
    
    def _start_lsl_relay(self):
        asyncio.run(cli.main_async(selected_device_info=self.info))
        


class frontVideo(QObject):
    displayed, recorded = False, False
    current_frame : np.array
    new_frame = Signal(float,float)        
    new_sample = Signal(float,dict)#timestamp, gaze and corresponding frame in the video
    running = False
    recordings_folder = ""
    def __init__(self, device, stream_name):
        super().__init__()
        self.stream_name, self.device = stream_name, device
        self.new_sample.connect(stream_recorder.onNewSample)       
        print("finished initializing PI video")
    
    def receive_video_and_gaze(self):
        
        self.running = True
        current_frame_index = 0
        while self.displayed or self.recorded:
            frame, gaze = self.device.receive_matched_scene_video_frame_and_gaze()
            self.current_frame = frame.bgr_pixels
            self.new_frame.emit(gaze.x, gaze.y)
            self.new_sample.emit(gaze.timestamp_unix_seconds,{ 'gaze_x':gaze.x,'gaze_y' : gaze.y,'corresponding_frame':current_frame_index} )
            
            if self.recorded:
                self.p.stdin.write(self.current_frame)
            
            current_frame_index += 1            
        self.running = False
    
    def save(self):
        self.p.stdin.close()
        self.p.wait()
     
    def stop_recording(self):
        print('frameVIdeo PI stopped running')
        self.recorded = False
        #self.save()


    def start_display(self):
        self.displayed = True
        if not self.running:
            threading.Thread(name = self.stream_name, target = self.receive_video_and_gaze).start()
    def start_recording(self):
        print("pi started recording")
        self.p = sp.Popen(shlex.split(f'ffmpeg -y -s {1080}x{1080} -pixel_format bgr8 -f rawvideo \
                                       -r {30} -i pipe: -vcodec libx264 -pix_fmt yuv420p -crf 15 \
                                           "{self.recordings_folder}/video_pi.mp4" '), stdin=sp.PIPE)
        self.recorded = True
        if not self.running:
            threading.Thread(name = self.stream_name, target = self.receive_video_and_gaze).start()

            
class videoWidget2(QWidget):
    def __init__(self, pi_device):
        import cv2
        super().__init__()
        self.resize(1080,1080) #dimensions of the frame received from pupil invisible device
        
        #initialize video box
        self.vidContainer = QLabel("",self)
        self.pixmap = QPixmap(1080,1080)
        self.pixmap.fill(QColor("black"))
        self.vidContainer.setPixmap(self.pixmap)
        
        #connect to corresponding frameVideo
        self.video = pi_device.streams["other"]["Vidéo Frontale"]

        self.video.new_frame.connect(self.onNewFrame)
        self.video.start_display()

    def onNewFrame(self, gaze_x, gaze_y):
        import cv2
        frame = self.video.current_frame
        cv2.circle( frame, (int(gaze_x), int(gaze_y)), radius=80, color=(0, 0, 255),thickness=15 )
        cv2.resize(frame, (self.width(), self.height()))
        h,w = frame.shape[:2]
        qimg = QImage(frame,w,h,QImage.Format_BGR888)
        self.vidContainer.setPixmap(QPixmap(qimg))      
        
supported_devices.append(piDevice)          
