'''
Created on Feb 3, 2021

@author: fgeissler
'''

import gerber
import tkinter as tk
from tkinter import filedialog
import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff
import KicadModTree as kmt
from math import sqrt, atan2, pi
import os

class GerberObject:
    def __init__(self, filename):
        self.gbr = gerber.read(filename)
        self._populateShapelyPrimitives()
        
        union = sop.unary_union(self.shapelyPrimitives)
        
        self.closedPolygons = [geo.polygon.orient(poly) for poly in union]
        self.polygonLines = []
        self.pads = []
        
        self.tolerance = 1e-6
        
        for poly in self.closedPolygons:
            boundary = poly.boundary
            
            for i in range(len(boundary.coords) - 1):
                self.polygonLines.append(geo.LineString([boundary.coords[i], boundary.coords[i + 1]]))
        
    def boundingBox(self):
        mp = geo.MultiPolygon(self.closedPolygons + self.pads)
        
        return mp.bounds
    
    def closedRegions(self):
        return self.closedPolygons
    
    def polyLines(self):
        return self.polygonLines
    
    def addPad(self, p):
        self.pads.append(p)
            
    def getPads(self):
        return self.pads
        
    def _populateShapelyPrimitives(self):
        self.shapelyPrimitives = []
        
        for p in self.gbr.primitives:
            if type(p) == gerber.primitives.Region:
                self.shapelyPrimitives = self.shapelyPrimitives + list(self._shapelyPolygon(p))
            else:
                print('Unsupported Primitive:', type(p))
                continue
            
    def _shapelyLine(self, gerber_line):
        return (gerber_line.start, gerber_line.end)
    
    def _shapelyPolygon(self, gerber_region):
        lines = []
        
        for p in gerber_region.primitives:
            # Check if type supported
            if type(p) == gerber.primitives.Line:
                lines.append(self._shapelyLine(p))
            else:
                print('Unsupported Primitive:', type(p))
                continue
            
        return sop.polygonize(lines)
    
    def exportToKicadMod(self, filename, footprint_name = 'EM-Structure', description="EM Structure imported from Gerber file format.", tags="em structure gerber" ):
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
        
        # iterate closed polygons
        for poly in self.closedPolygons:
            # find pads
            pads = []
            
            for p in self.pads:
                if(p.distance(poly) < self.tolerance):
                    pads.append(p)
                    
            if len(pads) == 0:
                # poly primitive        
                map = geo.mapping(poly)
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x + ox, -y - oy])
                
                mod.append(kmt.Polygon(nodes=coords, layer='F.Cu', width=0))
                
            else:
                # first pad is anchor
                anch = pads[0]
                
                # center point
                (pxmin, pymin, pxmax, pymax) = anch.bounds
                px = (pxmin + pxmax) / 2
                py = (pymin + pymax) / 2
                
                # size and rotation
                x1, y1 = anch.boundary.coords[0]
                x2, y2 = anch.boundary.coords[1]
                l = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                
                # set pad rotation and transform polygon accordingly
                rot_poly = aff.rotate(poly, -rot, (px, py))
                
                # poly primitive        
                map = geo.mapping(rot_poly)
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x - px, -(y - py)])
                
                kipoly = kmt.Polygon(nodes=coords)
                
                # create pad
                mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_CUSTOM, layers = ['F.Cu'], 
                                   at=[px + ox, -(py + oy)], size=[l, l], rotation=rot, primitives=[kipoly], anchor_shape=kmt.Pad.SHAPE_RECT))
                
                # other pads are simple squares
                for i in range(1, len(pads)):
                    # center point
                    (pxmin, pymin, pxmax, pymax) = pads[i].bounds
                    px = (pxmin + pxmax) / 2 + ox
                    py = -((pymin + pymax) / 2 + oy)
                    
                    # size and rotation
                    x1, y1 = pads[i].boundary.coords[0]
                    x2, y2 = pads[i].boundary.coords[1]
                    l = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                    rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                    
                    mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_RECT, layers = ['F.Cu'], 
                                       at=[px, py], size=[l, l], rotation=rot))
                
                # increase pad number
                n = n + 1
        
        # output kicad model
        file_handler = kmt.KicadFileHandler(mod)
        file_handler.writeFile(filename)
        

class GerberView(tk.Frame):
    def __init__(self, parent):
        super(GerberView, self).__init__(parent)

        ''' Load button '''
        self.btnLoad = tk.Button(root, command=self.btnLoadClick, text='Load Gerber File')
        self.btnLoad.pack()

        ''' Save button '''
        self.btnSave = tk.Button(root, command=self.btnSaveClick, text='Save KiCad Mod')
        self.btnSave.pack(padx = self.btnLoad.winfo_width())
        
        ''' Drawing canvas '''
        self.dwgGerber = tk.Canvas(root)
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
        
        self.gbr = GerberObject(self.filename)
        
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
        
        for r in self.gbr.closedRegions():
            self.drawRegion(r)
            
        for p in self.gbr.getPads():
            self.drawRegion(p)
        
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
    
    
    
    
    pass