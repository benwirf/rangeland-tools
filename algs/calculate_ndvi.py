from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import (Qt,
                            QCoreApplication,
                            QVariant,
                            QObject)

from qgis.PyQt.QtWidgets import (QWidget,
                                QLabel,
                                QSizePolicy,
                                QHBoxLayout,
                                QVBoxLayout)

from qgis.core import (QgsVectorLayer,
                        QgsMapLayerProxyModel,
                        QgsMapLayerType,
                        QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterRasterDestination)
                        
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
                        
from qgis.gui import (QgsMapLayerComboBox,
                        QgsRasterBandComboBox)

import processing

class CalculateNDVI(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "calculatendvi"
         
    def displayName(self):
        return "Calculate NDVI"
 
    def group(self):
        return "Raster General"
 
    def groupId(self):
        return "raster_general"
 
    def shortHelpString(self):
        return "Calculate Normalized Difference Vegetation Index."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        custom_widget_param = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input Parameters')
        custom_widget_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(custom_widget_param)
        
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Output NDVI raster'))
        
    def processAlgorithm(self, parameters, context, feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)[0]
        input_raster = custom_widget_inputs['Input Raster']#QgsRasterLayer
        red_band = custom_widget_inputs['Red Band']#Int
        nir_band = custom_widget_inputs['NIR Band']#int
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        #output_raster = parameters[self.OUTPUT]
        
        ###################################################################*****
        results = ['Calculation successful',
                    'Error creating output data file',
                    'Error reading input layer',
                    'User canceled calculation',
                    'Error parsing formula',
                    'Error allocating memory for result',
                    'Invalid band number for input',
                    'Error occurred while performing calculation']
                    
        ###*********************************************************************
        entries = []

        # Red Band
        b1_entry = QgsRasterCalculatorEntry()
        b1_entry.ref = 'red_band'
        b1_entry.raster = input_raster
        b1_entry.bandNumber = red_band
        entries.append(b1_entry)

        # NIR Band
        b2_entry = QgsRasterCalculatorEntry()
        b2_entry.ref = 'nir_band'
        b2_entry.raster = input_raster
        b2_entry.bandNumber = nir_band
        entries.append(b2_entry)

        expression = '("nir_band"-"red_band")/("nir_band"+"red_band")'
        bbox = input_raster.extent()
        crs = input_raster.crs()
        width = input_raster.width()
        height = input_raster.height()

        calc = QgsRasterCalculator(expression,
                                   output_raster,
                                   'GTiff',
                                   bbox,
                                   crs,
                                   width,
                                   height,
                                   entries)
                                   
        res = calc.processCalculation()
        #QMessageBox.information(self, 'NDVI Calculation', results[res], QMessageBox.Ok)
        if res == 0:
            feedback.pushInfo(results[res])
        else:
            feedback.reportError(results[res])
        calc = None
        del calc
        entries.clear()
        ###*********************************************************************
                    
        return {'Input Raster': input_raster, 'Red Band': red_band, 'NIR Band': nir_band, 'Output Raster': output_raster}

###########################WIDGET WRAPPER CLASS#################################
# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.cpw = NDVIWidget()
        return self.cpw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.cpw.get_params()
        
###########################CUSTOM WIDGET CLASS##################################
class NDVIWidget(QWidget):
    def __init__(self):
        super(NDVIWidget, self).__init__()
        ###
        self.cb_size_policy = QSizePolicy()
        self.cb_size_policy.setHorizontalPolicy(QSizePolicy.Preferred)
        self.cb_size_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self.cb_size_policy.setHorizontalStretch(1)
        ###
        self.lyr_lbl = QLabel('Input raster:', self)
        self.lyr_cb = QgsMapLayerComboBox(self)
        self.lyr_cb.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.lyr_cb.setSizePolicy(self.cb_size_policy)
        self.lyr_cb_layout = QHBoxLayout()
        self.lyr_cb_layout.addWidget(self.lyr_lbl)
        self.lyr_cb_layout.addWidget(self.lyr_cb)
        ###---
        self.red_band_lbl = QLabel('Select red band:', self)
        self.red_band_cb = QgsRasterBandComboBox(self)
        self.red_band_cb.setSizePolicy(self.cb_size_policy)
        self.red_band_cb_layout = QHBoxLayout()
        self.red_band_cb_layout.addWidget(self.red_band_lbl)
        self.red_band_cb_layout.addWidget(self.red_band_cb)
        ###---
        self.nir_band_lbl = QLabel('Select NIR band:', self)
        self.nir_band_cb = QgsRasterBandComboBox(self)
        self.nir_band_cb.setSizePolicy(self.cb_size_policy)
        self.nir_band_cb_layout = QHBoxLayout()
        self.nir_band_cb_layout.addWidget(self.nir_band_lbl)
        self.nir_band_cb_layout.addWidget(self.nir_band_cb)
        ###---
        ############################
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.lyr_cb_layout)
        self.main_layout.addLayout(self.red_band_cb_layout)
        self.main_layout.addLayout(self.nir_band_cb_layout)
        
        self.set_layer(self.lyr_cb.currentLayer())
        self.lyr_cb.layerChanged.connect(self.set_layer)
        
    def set_layer(self, current_lyr):
        if not current_lyr:
            return()
        if current_lyr.type() == QgsMapLayerType.RasterLayer:
            for cb in self.findChildren(QgsRasterBandComboBox):
                cb.setLayer(current_lyr)
                
    def get_params(self):
        input_raster = self.lyr_cb.currentLayer()
        red_band = self.red_band_cb.currentBand()
        nir_band = self.nir_band_cb.currentBand()
        ndvi_params = {'Input Raster': input_raster,
                        'Red Band': red_band,
                        'NIR Band': nir_band}
                        
        return [ndvi_params]
