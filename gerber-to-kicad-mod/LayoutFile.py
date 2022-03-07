'''
Created on Feb 21, 2022

@author: fgeissler
'''

import gerber
import ezdxf
import warnings
import os.path as path

import shapely.geometry as geo
import shapely.ops as sop

from numpy import poly

# TODO: Separate Classes for the different file types

class LayoutFile:
    '''
    Read Layout file formats and provide the polygon data
    '''
    def __init__(self):
        self.clear()
        
    def clear(self):
        '''
        Clears the imported polygon data.
        '''
        # Init layer dict
        self.layers = {}
    
    def read(self, filename, layer_prefix=''):
        '''
        Read a file and append the layer data.
        
        @param filename: The path to the file.
        @param layer_prefix: The prefix for the layer name, so multiple files do not merge.
        '''
        if not path.exists(filename):
            raise ValueError('Not an existing file name: %s' % (str(filename),))
        
        base, ext = path.splitext(filename)
        base = path.basename(base)
            
        if ext == ".dxf":
            self._read_dxf(filename, layer_prefix)
        elif (ext[0:2] == ".g") and (len(ext) == 4):
            warnings.warn('Assuming the extension "%s" to be a Gerber file.' % (ext,))
            self._read_gbr(filename, layer_prefix + base)
        else:
            raise ValueError('Unknown file extension: "%s".\nKnown extensions: Gerber *.gXX, DXF *.dxf' % (ext,))
            
    def _read_dxf(self, filename, layer_prefix):
        '''
        Read a dxf file.
        '''
        dxfdoc = ezdxf.readfile(filename)
        
        # Unit conversion
        unit = dxfdoc.units
        convf = ezdxf.units.conversion_factor(unit, ezdxf.units.MM)
        
        msp = dxfdoc.modelspace()
        self._read_dxf_recurse(msp, convf, layer_prefix)
            
        for k in self.layers.keys():
            print(k + ": " + str(self.layers[k]))
                
    def _read_dxf_recurse(self, entities, convf, pref):
        '''
        Recurse through dxf INSERTs (grouped entities).
        '''
        for e in entities:
            etype = e.dxftype()
            
            if etype == 'INSERT':
                self._read_dxf_recurse(e.virtual_entities(), convf, pref)
            elif etype == 'POLYLINE':
                self._read_dxf_polyline(e, convf, pref)
            else:
                warnings.warn('Entity type %s not supported by DXF importer!' % (etype,))
    
    def _read_dxf_polyline(self, ent, convf, pref):
        '''
        Generate a polygon from a dxf POLYLINE and union to layer.
        '''
        points = [[p.x * convf, p.y * convf] for p in ent.points()]
        self._union_layer_poly(geo.Polygon(points), pref + ent.dxf.layer)
        
    def _read_gbr(self, filename, layer):
        '''
        Read a Gerber file.
        '''
        # Parse gerber file
        gbr = gerber.read(filename)
        # Convert to metric units
        gbr.to_metric()
        # read file contents
        self._read_gbr_recurse(gbr.primitives, layer)
        
    def _read_gbr_recurse(self, primitives, layer):
        '''
        Recurse through gerber primitives.
        '''
        for p in primitives:
            ptype = type(p)
            
            if ptype == gerber.primitives.Region:
                self._read_gbr_region(p, layer)
            else:
                warnings.warn('Gerber primitive type %s not supported by Gerber importer!' % (str(ptype),))
        
    def _read_gbr_region(self, reg, layer):
        '''
        Read a gerber region.
        '''
        points = []
        
        for p in reg.primitives:
            ptype = type(p)
            
            if ptype == gerber.primitives.Line:
                points.append((p.start, p.end))
            else:
                warnings.warn('Gerber region primitive type %s not supported by Gerber importer!' % (str(ptype),))
        
        for poly in sop.polygonize(points):
            self._union_layer_poly(poly, layer)
        
    def _union_layer_poly(self, poly, layer):
        '''
        Union a polygon to the specified layer.
        '''
        if poly is None:
            raise ValueError('The parameter "poly" must be a valid shapely Polygon object!')
        if not layer:
            raise ValueError('The parameter "layer" must be a valid layer name string!')
        
        if layer in self.layers.keys():
            self.layers[layer] = poly.union(self.layers[layer])
        else:
            self.layers[layer] = poly

    def get_layer_names(self):
        '''
        Return a list of available layer names.
        '''
        return list(self.layers.keys())

    def get_layer_poly(self, layer):
        '''
        Return the Polygon of a specific layer.
        
        @param layer: The layer identifier.
        '''
        return self.layers[layer]
    
    def get_layers(self):
        '''
        Return the layers as dictionary.
        '''
        return self.layers

if __name__ == '__main__':
    f = LayoutFile()
    f.read('Coupler.gbr', 'layer_prefix:')

    print(f.get_layers())
    