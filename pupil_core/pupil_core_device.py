
import threading
import os
import time
import subprocess as sp

import pylsl
import zmq
import msgpack
import numpy as np
from msgpack import unpackb
from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QObject
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtGui import QPixmap, QImage, QColor
import nmap


from lib import supported_devices, get_ip, stream_recorder, partialclass, stream_recorder


class coreDevice:
    device_type = 'pupil_core'
    name: str
    widgets = {}
    streams = {'lsl': {"tout les streams" : "pupil_capture"},
               'other' : {'Vidéo Frontale': None}}
    active_streams = {"lsl": [], "other": []}
    
    ip: str
    ctx: zmq.Context 
    
    def discover(timeout = 7):
        threading.current_thread().name = "pupil-core-discovery"
        #scan for open pupil capture port on the local network
        nm = nmap.PortScanner()
        try:
            nm.scan(f'{get_ip()}/24', arguments = '--min-hostgroup 100 -n -T4 -p50020 -sV',timeout = timeout)
        except nmap.PortScannerTimeout:
            print("timeout was reached before scanning all hosts on the network, results may be incomplete")
        ips = up_hosts = [ x for x in nm.all_hosts() if nm[x]['tcp'][50020]['state'] == 'open']
        print("scanning for pupil-core devices")        
        ctx = zmq.Context()
        
        found_devices = []
        for ip in ips:
            found_devices.append(coreDevice(ip,ctx))
        print('found the following Pupil Core devices:', [dev.name for dev in found_devices] )
        return found_devices
            
    def __init__(self,ip,ctx):
        self.remote = zmq.Socket(ctx, zmq.REQ)
        self.remote.connect(f'tcp://{ip}:50020')
        self.ip = ip
        self.ctx = ctx
        self.name = f'PUPIL-CORE-{ip}'
        
        for k,v in self.streams['lsl'].items():
            self.streams['lsl'][k] = f"{v}"
        self.active_streams["lsl"] = list(self.streams["lsl"].values())
        
        self.connect()
        self.streams["other"]["Vidéo Frontale"] = frameVideo(self.sub, self.name+'_front_video')
        
        self.widgets = {"frontal video with gaze": partialclass(videoWidget,device = self,stream_name = "Vidéo Frontale") }
           
    def connect(self):          
        #connect to SUB port to receive data
        self.remote.send_string('SUB_PORT')
        sub_port = self.remote.recv_string()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(f'tcp://{self.ip}:{sub_port}')

        #connect to PUB port to publish data
        self.remote.send_string('PUB_PORT')
        pub_port = self.remote.recv_string()
        self.pub = self.ctx.socket(zmq.SUB)
        self.pub.connect(f'tcp://{self.ip}:{sub_port}')
        
        print(self.name,": connection Finished")
    
    def stream_lsl(self):
        pass

class frameVideo(QObject):
    displayed, recorded = False, False
    current_frame : np.array
    new_frame = Signal()        
    new_sample = Signal(float,dict)#timestamp, gaze and corresponding frame in the video
    running = False
    recordings_folder = ""
    def __init__(self, sub, stream_name, fps = 30):
        super().__init__()
        self.stream_name, self.sub, self.fps = stream_name, sub, fps
        sub.subscribe("frame.world")
        #sub.subscribe("gaze.3d.x")
        self.new_sample.connect(stream_recorder.onNewSample)
        
        print("finished initializing core video")
    
    def receive_video_and_gaze(self):

        self.running = True
        
        current_frame_index = 0
        while self.displayed or self.recorded:
            topic = self.sub.recv_string()
            payload = unpackb(self.sub.recv())
            
            if "frame.world" in topic:
                frames = []
                while self.sub.get(zmq.RCVMORE):
                    frames.append(self.sub.recv())
                if frames:
                    self.current_frame = frames[-1]
            self.new_frame.emit()
            self.new_sample.emit(10.2,{ 'gaze_x':None,'gaze_y' : None,'corresponding_frame':current_frame_index} )
            if self.recorded:
                self.p.stdin.write(self.current_frame)
            current_frame_index += 1            
        self.running = False
    
    def save(self):
        self.p.stdin.close()
        self.p.wait()
     
    def stop_recording(self):
        print('frameVIdeo core stopped running')
        self.recorded = False
        self.save()


    def start_display(self):
        self.displayed = True
        if not self.running:
            threading.Thread(name = self.stream_name, target = self.receive_video_and_gaze).start()
    def start_recording(self):
        self.p = sp.Popen(['ffmpeg', '-re','-y', '-f', 'image2pipe', '-r',str(self.fps),
                           '-i', '-', '-vcodec', 'copy', '-crf', '23', '-r',
                           str(self.fps), f'{self.recordings_folder}/frontal_video_core.mp4'], stdin=sp.PIPE) #'-vcodec', 'mjpeg',
        self.recorded = True
        if not self.running:
            threading.Thread(name = self.stream_name, target = self.receive_video_and_gaze).start()

            
class videoWidget(QWidget):
    def __init__(self, device, stream_name):
        #import cv2
        super().__init__()
        self.resize(640,480) #dimensions of the frame received from pupil invisible device
        
        #initialize video box
        self.vidContainer = QLabel("",self)
        self.pixmap = QPixmap(640,480)
        self.pixmap.fill(QColor("black"))
        self.vidContainer.setPixmap(self.pixmap)
        
        #connect to corresponding frameVideo
        self.video = device.streams["other"][stream_name]
        self.video.new_frame.connect(self.onNewFrame)
        self.video.start_display()

    def onNewFrame(self, gaze = None):
        import cv2
        frame = self.video.current_frame
        #cv2.circle( frame, (int(gaze.x), int(gaze.y)), radius=80, color=(0, 0, 255),thickness=15 )
        #frame = cv2.resize(frame, (self.width(), self.height()))
        qimg = QImage.fromData(frame)
        w,h =  qimg.width(), qimg.height()
        self.vidContainer.setPixmap(QPixmap(qimg))
            
supported_devices.append(coreDevice)  
