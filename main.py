#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 16 18:17:17 2022

@author: max
"""
#!/bin/python
import sys
import threading
from pprint import pprint
import functools

from PyQt5.QtCore import QMargins, Qt, pyqtSignal as Signal, pyqtSlot as Slot
from PyQt5.QtGui import QKeySequence, QResizeEvent
from PyQt5.QtWidgets import (QApplication,QMainWindow, QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QTabWidget, QLabel,
                             QShortcut, QFileDialog)

from DeviceColumn import deviceColumn
#from pupil_invisible import piDevice
#from pupil_core import coreDevice
#from smarting_eeg import smartingEEG
#from faros import farosDevice
from view_pane import viewPane
#from lib import change_recording, stream_recorder
from replay_bar import replayBar
from lib import replay_manager

def debug_print():
    pprint(threading.enumerate())  
       

class mainWindow(QWidget):
    resizeSignal = Signal(QResizeEvent)
    def __init__(self):    
        super().__init__()
        self.resize(1000, 1000)
        self.isMainWindow = True #to make it findable easily from scopes where mainWindow class is not defined
        
        self.setStyleSheet("margin: 0px; padding: 0px; spacing: 0px")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.view_pane = viewPane()
        self.layout.addWidget(self.view_pane, 90)
        
        self.replay_bar = replayBar()
        self.layout.addWidget(self.replay_bar, 10)
        
        
        self.devCol = deviceColumn(self)
        self.hide_devcol_button = QPushButton("-", parent = self)
        self.hide_devcol_button.clicked.connect(self.hide_devcol)
        self.hide_devcol_button.resize(50,40)
        
        replay_manager.timer.start(replay_manager.step)
        
        
    def hide_devcol(self):
        if self.devCol.isVisible():
            self.devCol.hide()
            self.hide_devcol_button.setText("+")
        else:
            self.devCol.show()
            self.hide_devcol_button.setText("-")
            
    def resizeEvent(self,event):
        self.resizeSignal.emit(event)
        w,h = event.size().width(), event.size().height()
        self.hide_devcol_button.move(w-self.hide_devcol_button.width(),0)
        super().resizeEvent(event)
        
        
        
        

        


    

               
app = QApplication([])
win = mainWindow()
win.move(0,0)
win.show()
sys.exit(app.exec())


"""
self.wid = QWidget(self)
#self.wid.setStyleSheet("background-color: black")
self.wid.resize(self.size())
self.wid.setAttribute(Qt.WA_TransparentForMouseEvents, True)
self.wid.layout = QHBoxLayout(self.wid)
self.wid2 = QWidget()
self.wid2.setStyleSheet('background-color: black')
self.wid.layout.addWidget(self.wid2)
"""