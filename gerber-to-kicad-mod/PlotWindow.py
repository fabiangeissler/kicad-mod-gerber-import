#!/usr/bin/env python

'''
Created on Feb 6, 2021

@author: fgeissler
'''

'''
TODO: delete pads
TODO: multiple layers
'''

# matplotlib
import matplotlib.pyplot as plt
import matplotlib.widgets as wid
import matplotlib.colors as col
import matplotlib as mpl
from matplotlib.backend_bases import MouseButton

# shapely
import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff

# descartes
from descartes.patch import PolygonPatch

# tkinter (filedialog)
from tkinter import filedialog
import tkinter as tk

import os
from GerberLayer import GerberLayer

from math import sqrt
import KicadModTree as kmt

class PlotWindow(object):
    MOUSE_NONE = 0
    MOUSE_PAN = 1
    MOUSE_DRAG = 2
    
    def __init__(self):
        # Disable default Toolbar and enable interactive mode
        mpl.rcParams['toolbar'] = 'None'
        plt.ion()
        
        # New figure
        self.fig = plt.figure()
        
        # Data Axes
        self.ax = self.fig.add_subplot(111)
        self.ax.grid(which='major')
        # default viewport
        self.ax.set_xlim([-10, 10])
        self.ax.set_ylim([-10, 10])
        # fixed aspect ratio
        self.ax.set_aspect('equal', adjustable='datalim')
        # labels
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        
        # Pad prototype
        self.padProto = None
        self.padProtoPoly = None
        self.padProtoEdge = None
        self.padProtoNet = None
        self.padWidth = 0
        self.padHeight = 0
        
        # Load Button
        self.bloadAx = self.fig.add_axes([0.01, 0.9, 0.25, 0.075])
        self.bload = wid.Button(self.bloadAx, 'Load Gerber Layer')
        self.bload.on_clicked(self._bloadClick)
        
        # Save Button
        self.bsaveAx = self.fig.add_axes([0.27, 0.9, 0.25, 0.075])
        self.bsave = wid.Button(self.bsaveAx, 'Save KiCad Module')
        self.bsave.on_clicked(self._bsaveClick)
        
        # Pad size input
        self.twidthAx = self.fig.add_axes([0.65, 0.9, 0.1, 0.075])
        self.twidth = wid.TextBox(self.twidthAx, 'Pad W', initial=str(self.padWidth))
        self.twidth.on_submit(self._twidthSubmit)
        
        # Pad size input
        self.theightAx = self.fig.add_axes([0.85, 0.9, 0.1, 0.075])
        self.theight = wid.TextBox(self.theightAx, 'Pad H', initial=str(self.padHeight))
        self.theight.on_submit(self._theightSubmit)
        
        # Layers
        self.gerberLayers = []
        self.activeLayer = None
        
        # Patches
        self.polyPatches = []
        
        # Highlight shape
        self.highlight = None
        
        # Mouse position
        self.mouseDownX = 0
        self.mouseDownY = 0
        # Mouse Mode
        self.mouseMode = self.MOUSE_NONE
        # Scroll factor
        self.mouseScrollFact = 1.1
        # Maximum click time
        self.mouseClickTime = 0.25
        # center pad pixel distance
        self.centerPadDist = 10
        self.selectDist = 20
    
        # Mouse events
        self.fig.canvas.mpl_connect('button_press_event', self._mouseDown)
        self.fig.canvas.mpl_connect('button_release_event', self._mouseUp)
        self.fig.canvas.mpl_connect('motion_notify_event', self._mouseMove)
        self.fig.canvas.mpl_connect('scroll_event', self._mouseScroll)
    
    def _twidthSubmit(self, text):
        self.padWidth = float(text)
        
    def _theightSubmit(self, text):
        self.padHeight = float(text)
    
    def _bloadClick(self, event):
        fname = filedialog.askopenfilename()
        
        if os.path.exists(fname):
            self.gerberLayers.append(GerberLayer(filename = fname))
            self.generateLayers()
            
            if len(self.gerberLayers) > 0:
                self.activeLayer = self.gerberLayers[0]
    
    def _bsaveClick(self, event):
        filename = filedialog.asksaveasfilename(initialfile='em-structure.kicad_mod', defaultextension=".kicad_mod",filetypes = (("KiCad Module","*.kicad_mod"),("All Files","*.*")))
        
        if os.access(os.path.dirname(filename), os.W_OK):
            self.exportKiCadModule(filename)
    
    def _mouseDown(self, event):
        if (event.xdata == None) or (event.ydata == None):
            return
        
        # Mouse Down location
        self.mouseDownX = event.xdata
        self.mouseDownY = event.ydata
        
        # Mouse Button to select Mode
        if event.button == MouseButton.LEFT:
            self.padProtoEdge, self.padProtoNet = self._edgeNetInDist(event.x, event.y)
    
            if self.padProtoEdge == None:
                return
            
            self.mouseMode = self.MOUSE_DRAG
            
        elif event.button == MouseButton.MIDDLE:
            self.mouseMode = self.MOUSE_PAN
    
    def _mouseUp(self, event):    
        # remove pad prototype
        if self.padProto != None:
            if self.mouseMode == self.MOUSE_DRAG:
                self.padProtoNet.addPad(self.padProtoPoly)
                patch = self.plotPoly(self.padProtoPoly, self.activeLayer.getColor())
                self.polyPatches.append(patch)
                
            self.padProto.remove()
            self.padProto = None
            
        
        self.mouseMode = self.MOUSE_NONE 
    
    def _mouseScroll(self, event):
        if (event.xdata == None) or (event.ydata == None):
            return
        
        if(event.button == 'up'):
            scale = self.mouseScrollFact
        elif(event.button == 'down'):
            scale = 1/self.mouseScrollFact
        else:
            return
        
        x1, x2 = self.ax.get_xlim()
        y1, y2 = self.ax.get_ylim()
        
        self.ax.set_xlim([event.xdata - (event.xdata - x1) * scale, 
                          event.xdata - (event.xdata - x2) * scale])
        self.ax.set_ylim([event.ydata - (event.ydata - y1) * scale, 
                          event.ydata - (event.ydata - y2) * scale])
    
    def _edgeNetInDist(self, x, y, d = 25):
        if self.activeLayer == None:
            return None, None
        
        tm = self.ax.transData.inverted()
        xdata, ydata = tm.transform((x, y))
        x2, _ = tm.transform((x + d, y))
        maxdist = x2 - xdata
        
        # get closest net
        net, dist = self.activeLayer.closestNet(xdata, ydata)
        
        # exit if not close enough
        if(dist > maxdist):
            return None, None
        
        # closest edge of net
        edge, dist = net.closestEdge(xdata, ydata)
        
        # exit if edge not close enough
        if(dist > maxdist):
            return None, net
        
        return edge, net
    
    def _edgeNormal(self, edge):
        x1, y1 = edge.coords[0]
        x2, y2 = edge.coords[1]
        
        dx = (x2 - x1)
        dy = (y2 - y1)
        llen = sqrt(dx ** 2 + dy ** 2)
        
        nx = dy / llen
        ny = -dx / llen
        
        return nx, ny
    
    def _mouseMove(self, event):
        # remove existing pad prototype
        if self.highlight != None:
            self.highlight.remove()
            self.highlight = None
                
        if self.mouseMode == self.MOUSE_PAN:   
            tm = self.ax.transData.inverted()
            xdata, ydata = tm.transform((event.x, event.y))
             
            dx = self.mouseDownX - xdata
            dy = self.mouseDownY - ydata
            
            x1, x2 = self.ax.get_xlim()
            y1, y2 = self.ax.get_ylim()
            
            self.ax.set_xlim([x1 + dx, x2 + dx])
            self.ax.set_ylim([y1 + dy, y2 + dy])
            
        elif self.mouseMode == self.MOUSE_DRAG:
            tm = self.ax.transData.inverted()
            xdata, ydata = tm.transform((event.x, event.y))
            x2, _ = tm.transform((event.x + self.centerPadDist, event.y))
            cdist = x2 - xdata
                        
            nx, ny = self._edgeNormal(self.padProtoEdge)
            d = nx * (xdata - self.mouseDownX) + ny * (ydata - self.mouseDownY)
        
            if abs(d) < cdist:
                s = 0
            elif d < 0:
                s = -1
            else:
                s = 1
        
            self.padProtoPoly = self.padProtoNet.generateRectPad(self.padProtoEdge, shift=s, width=self.padWidth, height=self.padHeight)
            
            # remove existing pad prototype
            if self.padProto != None:
                self.padProto.remove()
                
            self.padProto = self.plotPoly(self.padProtoPoly, '#A0A0FF80')
            #net.addPad(padPoly)
        else:
            if self.activeLayer == None:
                return
            
            edge, _ = self._edgeNetInDist(event.x, event.y, self.selectDist)
    
            if edge == None:
                return
                
            self.highlight = self.ax.plot(*edge.xy, '#20E020').pop(0)
        
    def plotPoly(self, p, c):
        patch = PolygonPatch(p, facecolor=c)
        self.ax.add_patch(patch)
        
        return patch
        
    def generateLayers(self):
        self.clear()
        
        for layer in self.gerberLayers:
            multipoly = layer.getMultiPolygon()
            
            for poly in multipoly:
                patch = self.plotPoly(poly, layer.getColor())
                self.polyPatches.append(patch)
        
    def clear(self):
        for patch in self.polyPatches:
            patch.remove()
        
    def setViewport(self, minx, miny, maxx, maxy):
        self.ax.set_xlim([minx, maxx])
        self.ax.set_ylim([miny, maxy])
    
    def boundingBox(self):
        return self.activeLayer.boundingBox()    
    
    def exportKiCadModule(self, filename, footprint_name = 'EM-Structure', description="EM Structure imported from Gerber file format.", tags="em structure gerber" ):
        mod = kmt.Footprint(footprint_name)
        mod.setDescription(description)
        mod.setTags(tags)
        
        # set general values
        mod.append(kmt.Text(type='reference', text='REF**', at=[0, -3], layer='F.SilkS'))
        mod.append(kmt.Text(type='value', text=footprint_name, at=[1.5, 3], layer='F.Fab'))
        
        # create silscreen
        #mod.append(kmt.RectLine(start=[-2, -2], end=[5, 2], layer='F.SilkS'))
        
        (minx, miny, maxx, maxy) = self.boundingBox()
        w = maxx - minx
        h = maxy - miny
        ox = - maxx + w/2
        oy = - maxy + h/2
        
        # create courtyard
        mod.append(kmt.RectLine(start=[-w/2, -h/2], end=[w/2, h/2], layer='F.CrtYd'))
        #mod.append(kmt.FilledRect(start=[-w/2, -h/2], end=[w/2, h/2], layer='F.Mask'))
        
        n = 1
        
        # iterate layers
        for layer in self.gerberLayers:
            n = layer.appendKicadLayer(mod, mod_layer=layer.getID(), offset_x = ox, offset_y = oy, startpad=n)
        
        # output kicad model
        file_handler = kmt.KicadFileHandler(mod)
        file_handler.writeFile(filename)
        
if __name__ == '__main__':

    tk.Tk().withdraw()
    t = PlotWindow()
    plt.show(block=True)
    