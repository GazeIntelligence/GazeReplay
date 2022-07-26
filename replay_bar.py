# -*- coding: utf-8 -*-

from functools import partial

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSlider, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal as Signal

from lib import replay_manager


class replayBar(QWidget):
    time_changed = Signal(int)
    
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        
        self.time_slider = QSlider(Qt.Horizontal)
        
        self.time_slider.setMinimum(replay_manager.time_range[0])
        self.time_slider.setMaximum(replay_manager.time_range[1])
        self.layout.addWidget(self.time_slider)
        self.time_slider.setTickInterval(1000)
        self.time_slider.setTickPosition(QSlider.TicksBelow)
        
        self.time_slider.sliderMoved.connect(replay_manager.on_time_changed)
        self.time_slider.sliderPressed.connect(replay_manager.timer.stop)
        self.time_slider.sliderReleased.connect(partial(replay_manager.timer.start, replay_manager.step))
        
        replay_manager.time_changed.connect(self.adjust_slider)
        
    def adjust_slider(self, time):
        self.time_slider.setValue(time)
