'''
Created on Feb 4, 2021

@author: fgeissler
'''
import tkinter as tk
from tkinter import filedialog
import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff
import KicadModTree as kmt
from math import sqrt, atan2, pi
import os

from GerberLayer import GerberLayer

class GerberView(tk.Frame):
    def __init__(self, parent):
        super(GerberView, self).__init__(parent)

        ''' Load button '''
        self.btnLoad = tk.Button(parent, command=self.btnLoadClick, text='Load Gerber File')
        self.btnLoad.pack()

        ''' Save button '''
        self.btnSave = tk.Button(parent, command=self.btnSaveClick, text='Save KiCad Mod')
        self.btnSave.pack(padx = self.btnLoad.winfo_width())
        
        ''' Drawing canvas '''
        self.dwgGerber = tk.Canvas(parent)
        self.dwgGerber.bind("<Button-1>", self.dwgGerberClick)
        self.dwgGerber.pack(pady=self.btnLoad.winfo_height(), fill=tk.BOTH, expand=tk.YES)
        
        ''' Filename '''
        self.filename = None
        
        ''' Gerber Object '''
        self.gbr = None
        
    ''' Load button click. Select the file name '''
    def btnLoadClick(self):
        self.filename = filedialog.askopenfilename()
        
        if os.path.exists(self.filename):
            self.readGerber()
        
    ''' Load button click. Select the file name '''
    def btnSaveClick(self):
        filename = filedialog.asksaveasfilename(initialfile='em-structure.kicad_mod', defaultextension=".kicad_mod",filetypes = (("KiCad Module","*.kicad_mod"),("All Files","*.*")))
        
        if os.access(os.path.dirname(filename), os.W_OK):
            self.gbr.exportToKicadMod(filename)
        
    ''' Load button click. Select the file name '''
    def dwgGerberClick(self, event):
        clklines = []
        
        for l in self.gbr.polyLines():
            if l.distance(geo.Point(*self.getGerberCoord(event.x, event.y))) < self.getGerberDist(5):
                clklines.append(l)
                
        if len(clklines) > 1:
            print('Ambiguous selection!')
        elif len(clklines) == 0:
            print('No line hit!')
        else:
            print('Creating pad anchor...')
            
            line = clklines[0]
            map = geo.mapping(line)
            x1 = map['coordinates'][0][0]
            y1 = map['coordinates'][0][1]
            x2 = map['coordinates'][1][0]
            y2 = map['coordinates'][1][1]
                
            poly = geo.Polygon([(x2,y2), (x1,y1), (x1+(y2-y1),y1-(x2-x1)), (x2+(y2-y1),y2-(x2-x1))])
            self.gbr.addPad(poly)
            self.drawGerber()
            self.drawLine(line)
        
    def readGerber(self):
        if(self.filename == None):
            return
        
        self.gbr = GerberLayer(filename=self.filename)
        
        self.drawGerber()
            
    def drawGerber(self):
        if(self.gbr == None):
            return
        
        self.dwgGerber.delete('all')
        
        # get bounding box:
        (minx, miny, maxx, maxy) = self.gbr.boundingBox()
        
        # transformations
        self.view_margin = 5
        self.view_height = self.dwgGerber.winfo_height() - 2 * self.view_margin
        self.view_width = self.dwgGerber.winfo_width() - 2 * self.view_margin
        self.translate_x = -minx
        self.translate_y = -miny
        self.scale_x = min(self.view_width / (maxx - minx), self.view_height / (maxy - miny))
        self.scale_y = self.scale_x
        
        for poly in self.gbr._getMultiPolygon():
            self.drawRegion(poly)
            
        #for p in self.gbr.getPads():
        #    self.drawRegion(p)
        
    def getViewCoord(self, x, y):
        sx = (x + self.translate_x) * self.scale_x + self.view_margin
        sy = self.view_height - (y + self.translate_y) * self.scale_y + self.view_margin
        
        return (sx, sy)
        
    def getGerberCoord(self, sx, sy):
        x = (sx - self.view_margin) / self.scale_x - self.translate_x
        y = -(sy - self.view_height - self.view_margin) / self.scale_y - self.translate_y
        
        return (x, y)
    
    def getGerberDist(self, d):
        return d / self.scale_x
    
    def drawLine(self, l):
        map = geo.mapping(l)
        coords = ()
        
        for xy in map['coordinates']:
            coords = coords + self.getViewCoord(*xy)
        
        self.dwgGerber.create_line(*coords, width = 2, fill = '#FF0000')
        
    def drawRegion(self, r):
        map = geo.mapping(r)
        coords = ()
        
        for xy in map['coordinates'][0]:
            coords = coords + self.getViewCoord(*xy)
        
        self.dwgGerber.create_polygon(coords, outline='#000000', fill='#FFF0E0')

if __name__ == '__main__':
    root = tk.Tk()
    
    # Load button
    gview = GerberView(root)
    gview.pack(padx = 0, pady = 0)
    
    root.geometry("400x250+300+300")
    root.mainloop()


