from functools import partial


from PyQt5.QtCore import  pyqtSignal as Signal
from PyQt5.QtWidgets import *

from lib import getMainWindow, replay_manager
from dummy_device import dummyDeviceReplay



class deviceColumn(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.resize(300,550)
        self.raise_() #should appear over the control bar
        self.move(parent.width() - self.width(),0) #place in top right corner ..
        parent.resizeSignal.connect(self.onParentResize) # .. and stick there on window resize
        self.setStyleSheet('margin: 0px')  
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0) #if not set there is a gap from the device column to the top of the window
        
        #set up the scroll area containing device boxes
        self.deviceScroll = QScrollArea(self)      
        self.deviceScroll.setWidgetResizable(True)       
        self.deviceScroll.setWidget(QWidget())
        
        self.devBox = QVBoxLayout()
        self.devBox.setContentsMargins(0,5,0,5)
        self.deviceScroll.widget().setLayout(self.devBox)
        
        self.layout.addWidget(self.deviceScroll, 100) 
        
        #add device boxes for active device shown on the save file
        self.add_devices_from_recording()

    def addDeviceBox(self,device):
        self.devBox.insertWidget(0,activeDeviceBox(device))
    
    def onParentResize(self,event):
        w,h = event.size().width(), event.size().height()
        self.move(w-self.width(),0)

        old_w, old_h = event.oldSize().width(), event.oldSize().height()

    def add_devices_from_recording(self):
        df = replay_manager.df
        stream_config = replay_manager.config["streams"]
        for device_name,streams in stream_config.items():
            if device_name != 'gaze marker stream':
                dev_type= streams[0]['device type']
                dev = eval(dev_type+'Replay')
                self.addDeviceBox(dev(device_name,streams))
            

            
        
class activeDeviceBox(QWidget):
    def __init__(self, device):
        super().__init__()
        #self.setMinimumHeight(1000)
        self.layout = QVBoxLayout(self)
        
        self.titleBar = QLabel(device.name)
        self.layout.addWidget(self.titleBar)
        
        self.tabBox = QTabWidget()
        self.layout.addWidget(self.tabBox)
        
        self.viewTab, self.streamTab = view_tab(device), stream_tab(device)      
        self.tabBox.addTab(self.viewTab,"View")
        self.tabBox.addTab(self.streamTab,"Streams")

        
class view_tab(QWidget):
    def __init__(self,device):
        super().__init__()
        add_vp = Signal(str)
        
        view_pane = getMainWindow().view_pane

        self.layout = QVBoxLayout(self)
        for title, view in device.views.items():
            view_button = QPushButton(title)
            self.layout.addWidget(view_button)  
            view_button.clicked.connect(partial(view_pane.add_widget,
                                                view = view,device = device))
            

def add_to_view_pane(wid,device,view_pane):

    w = wid()
    w.setStyleSheet("background-color: black")

    view_pane.layout.addWidget(w)
    view_pane.layout.activate()
    view_pane.layout.update()
    
            
class stream_tab(QWidget):
    def __init__(self, device):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        #create checkbox for every lsl stream on the device (checked if active )
        for _ , stream in device.streams.items():
            checkbox = QCheckBox(stream["display title"])                
            if stream["active"]:
                checkbox.setChecked(True)
            checkbox.setEnabled(False)
            self.layout.addWidget(checkbox)



    