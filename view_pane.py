#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 24 10:20:56 2022

@author: max
"""
import sys
from functools import partial
import json

from PyQt5.QtWidgets import (QApplication,QMainWindow, QHBoxLayout, QPushButton, QWidget, QTabWidget, 
                             QGridLayout, QGraphicsScene, QGraphicsView, QGraphicsItem, QLabel, QGraphicsRectItem,
                             QGraphicsTextItem)
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtGui import QBrush, QPen, QPainter, QColor
from PyQt5.QtCore import Qt, QRectF



class viewPane(QTabWidget):
    def __init__(self):
        super().__init__()
        self.resize(800,800)
        
        self.scene = QGraphicsScene(self)
        self.maxZ = 0
        self.scene.focusItemChanged.connect(self.sendToTop)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.view = QGraphicsView(self.scene, self)
        
        #disable the autoscrolling
        content_rect = self.view.contentsRect()
        self.view.setSceneRect(0, 0, content_rect.width(), content_rect.height())
           
        self.layout.addWidget(self.view)
        
        
        #self.add_widget(QPushButton)
    def sendToTop(self,newFocus,OldFocus,reason):
        if newFocus:
            newFocus.setZValue(self.maxZ+1)
            if newFocus.parentItem():
                newFocus.parentItem().setZValue(self.maxZ+1)
        self.maxZ += 1
    
    def add_widget(self , view,device = None, x = 100, y = 100): 
        #create the movable band on top of the widget
        wid = view["wid"]()
        title = view["stream"]["display title"] + ' from ' + view["stream"]["device"]   
        control_rect = controlRect(self.scene, wid, x, y, wid.width(), wid.height()+15, title = title)
        self.scene.setFocusItem(control_rect)
        self.scene.addItem(control_rect)
        self.sendToTop(control_rect, None, None)


class controlRect(QGraphicsRectItem):
    def __init__(self,scene, wid, x, y, w, h, title = None):
        super().__init__(x, y, w, h)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        #necessary to allow the scene to layer the last clicked object on top of the others
        self.setFlag(QGraphicsItem.ItemIsSelectable,True) 
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        
        self.setPen(QPen(QBrush(QColor('grey')), 3))
        self.setBrush(QBrush(QColor('white')))
        self.selected_edge = None
        self.click_pos = self.click_rect = None
        self.proxy = scene.addWidget(wid)
        self.proxy.setParentItem(self)
        self.proxy.setPos(x,y+15)
        self.proxy.setZValue(self.zValue()-10)
        
        self.title_line = QGraphicsTextItem(title,parent = self)
        self.title_line.setPos(x + w/2 - self.title_line.boundingRect().width()/2,y-5)
        
        self.quit_button = QGraphicsRectItem( -3 -10 , y + 3, 10, 10, parent = self)
        self.quit_button.setBrush(QBrush(QColor('red')))
        self.quit_button.mousePressEvent = lambda event : scene.removeItem(self)
        self.quit_button.setPos(self.boundingRect().x() + self.boundingRect().width(),
                                0)
        self.og_pos = (x,y,w,h)
        
    def mousePressEvent(self, event):
        """ The mouse is pressed, start tracking movement. """
        self.click_pos = event.pos()
        rect = self.rect()
        
        if abs(rect.top() - self.click_pos.y()) + abs(rect.left() - self.click_pos.x()) < 10:
            self.selected_edge = 'topleft'
        elif abs(rect.top() - self.click_pos.y()) + abs(rect.right() - self.click_pos.x()) < 10:
            self.selected_edge = 'topright'
        elif abs(rect.bottom() - self.click_pos.y()) + abs(rect.right() - self.click_pos.x()) < 10:
            self.selected_edge = 'bottomright'
        elif abs(rect.bottom() - self.click_pos.y()) + abs(rect.left() - self.click_pos.x()) < 10:
            self.selected_edge = 'bottomleft'
            
        elif abs(rect.left() - self.click_pos.x()) < 5:
            self.selected_edge = 'left'
        elif abs(rect.top() - self.click_pos.y()) < 5:
            self.selected_edge = 'top'
        elif abs(rect.right() - self.click_pos.x()) < 5:
            self.selected_edge = 'right'
        elif abs(rect.bottom() - self.click_pos.y()) < 5:
            self.selected_edge = 'bottom'
            
        else:
            self.selected_edge = None
        self.click_pos = event.pos()
        self.click_rect = rect
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """ Continue tracking movement while the mouse is pressed. """
        minW, minH = self.proxy.minimumWidth(), self.proxy.minimumHeight()
        
        # Calculate how much the mouse has moved since the click.
        pos = event.pos()
        x_diff = pos.x() - self.click_pos.x()
        y_diff = pos.y() - self.click_pos.y()

        # Start with the rectangle as it was when clicked.
        rect = QRectF(self.click_rect)
        
        if self.selected_edge == 'topleft':
            rect.adjust(x_diff, y_diff, 0, 0)
        elif self.selected_edge == 'topright':
            rect.adjust(0, y_diff, x_diff, 0)
        elif self.selected_edge == 'bottomright':
            rect.adjust(0, 0, x_diff, y_diff)
        elif self.selected_edge == 'bottomleft':
            rect.adjust(x_diff, 0, 0, y_diff)
            
        elif self.selected_edge == 'top':
            rect.adjust(0, y_diff, 0, 0)
        elif self.selected_edge == 'left':
            rect.adjust(x_diff, 0, 0, 0)
        elif self.selected_edge == 'bottom':
            rect.adjust(0, 0, 0, y_diff)
        elif self.selected_edge == 'right':
            rect.adjust(0, 0, x_diff, 0)
        
        # Also check if the rectangle has been dragged inside out.
        if rect.width() < (minH + 5):
            if self.selected_edge == 'left':
                rect.setLeft(rect.right() - (minH + 5))
            else:
                rect.setRight(rect.left() + (minH + 5))
        if rect.height() < minW + 5:
            if self.selected_edge == 'top':
                rect.setTop(rect.bottom() - (minW + 5))
            else:
                rect.setBottom(rect.top() + (minW +5))
        
        # Finally, update the rect that is now guaranteed to stay in bounds.
        self.setRect(rect)
        rect.adjust(0,15,0,0)
        self.proxy.setGeometry(rect)
        x,y,w,h = self.boundingRect().x(), self.boundingRect().y(), self.boundingRect().width(), self.boundingRect().height()
        self.quit_button.setPos(x+w, y - self.og_pos[1])
        
        #hides the text if the box is too to contain it
        if  self.title_line.boundingRect().width() < w: 
            if not self.title_line.isVisible():
                self.title_line.show()
            self.title_line.setPos(x + w/2 - self.title_line.boundingRect().width()/2,y-5)
        else :
            self.title_line.hide()
            
        if not self.selected_edge:
            super().mouseMoveEvent(event)

if __name__ == '__main__':
    app = QApplication([])
    win = viewPane()
    win.show()
    sys.exit(app.exec())