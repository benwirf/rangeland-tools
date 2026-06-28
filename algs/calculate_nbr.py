#WORKING VERSION May 2026
from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import (Qt,
                            QCoreApplication,
                            QVariant,
                            QObject)

from qgis.PyQt.QtWidgets import (QWidget,
                                QTabWidget,
                                QLabel,
                                QPushButton,
                                QHBoxLayout,
                                QFileDialog,
                                QGridLayout)

from qgis.core import (QgsVectorLayer,
                        QgsMapLayerProxyModel,
                        QgsMapLayerType,
                        QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterRasterDestination,
                        QgsProcessingException,
                        QgsProcessingUtils)
                        
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
                        
from qgis.gui import (QgsMapLayerComboBox,
                        QgsRasterBandComboBox)

from pathlib import Path

import processing

class CalculateNBR(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "calculatenbr"
         
    def displayName(self):
        return "Calculate normalised burn ratio"
 
    def group(self):
        return "Fire Mapping"
 
    def groupId(self):
        return "fire_mapping"
 
    def shortHelpString(self):
        return "Perform raster calculations on a multi-band input satellite raster\
        to generate 4 different commonly used Normalised Burn Ratio indices."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        custom_widget_param = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input Parameters')
        custom_widget_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(custom_widget_param)
        
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Output NBR raster'))
        
    def processAlgorithm(self, parameters, context, feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        #output_raster = parameters[self.OUTPUT]
        input_raster = custom_widget_inputs[0]
        ###################################################################*****
        results = ['Calculation successful',
                    'Error creating output data file',
                    'Error reading input layer',
                    'User canceled calculation',
                    'Error parsing formula',
                    'Error allocating memory for result',
                    'Invalid band number for input',
                    'Error occurred while performing calculation']
                    
        rc_expressions = {'NBR': '("nir_band"-"swir_band")/("nir_band"+"swir_band")',#NIR band is B8 (Sentinel)
                        'NBR 2': '("nir_band"-"swir_band")/("nir_band"+"swir_band")',#NIR band is B8A (Sentinel)
                        'NBR SWIR': '("swir2_band"-"swir1_band"-0.02)/("swir2_band"+"swir1_band"+0.1)',#B12 & B11 (Sentinel)
                        'NBR+': '("swir2_band"-"nir_band"-"green_band"-"blue_band")/("swir2_band"+"nir_band"+"green_band"+"blue_band")'}#B12, B8A, B3 & B2 (Sentinel)
        
        nbr_index = custom_widget_inputs[1]
        
        if nbr_index == 'NBR':
            rc_entries = []
            ###
            nir_entry = QgsRasterCalculatorEntry()
            nir_entry.ref = 'nir_band'
            nir_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B12[SWIR]': 1, 'B8[NIR]': 1}
            nir_entry.bandNumber = custom_widget_inputs[2]['B8[NIR]']
            rc_entries.append(nir_entry)

            swir_entry = QgsRasterCalculatorEntry()
            swir_entry.ref = 'swir_band'
            swir_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B12[SWIR]': 1, 'B8[NIR]': 1}
            swir_entry.bandNumber = custom_widget_inputs[2]['B12[SWIR]']
            rc_entries.append(swir_entry)
            
            rc_expression = rc_expressions[nbr_index]
            bbox = input_raster.extent()
            crs = input_raster.crs()
            width = input_raster.width()
            height = input_raster.height()

            calc = QgsRasterCalculator(rc_expression,
                                       output_raster,
                                       'GTiff',
                                       bbox,
                                       crs,
                                       width,
                                       height,
                                       rc_entries)
                                       
            res = calc.processCalculation(feedback)
            feedback.pushInfo(results[res])
            calc = None
            del calc
            rc_entries.clear()
        #-------
        elif nbr_index == 'NBR 2':
            rc_entries = []
            ###
            nir_entry = QgsRasterCalculatorEntry()
            nir_entry.ref = 'nir_band'
            nir_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B12[SWIR]': 1, 'B8A[NIR]': 1}
            nir_entry.bandNumber = custom_widget_inputs[2]['B8A[NIR]']
            rc_entries.append(nir_entry)

            swir_entry = QgsRasterCalculatorEntry()
            swir_entry.ref = 'swir_band'
            swir_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B12[SWIR]': 1, 'B8A[NIR]': 1}
            swir_entry.bandNumber = custom_widget_inputs[2]['B12[SWIR]']
            rc_entries.append(swir_entry)
            
            rc_expression = rc_expressions[nbr_index]
            bbox = input_raster.extent()
            crs = input_raster.crs()
            width = input_raster.width()
            height = input_raster.height()

            calc = QgsRasterCalculator(rc_expression,
                                       output_raster,
                                       'GTiff',
                                       bbox,
                                       crs,
                                       width,
                                       height,
                                       rc_entries)
                                       
            res = calc.processCalculation(feedback)
            feedback.pushInfo(results[res])
            calc = None
            del calc
            rc_entries.clear()

        elif nbr_index == 'NBR SWIR':
            rc_entries = []
            ###
            swir1_entry = QgsRasterCalculatorEntry()
            swir1_entry.ref = 'swir1_band'
            swir1_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B11[SWIR1]': 1, 'B12[SWIR2]': 1}
            swir1_entry.bandNumber = custom_widget_inputs[2]['B11[SWIR1]']
            rc_entries.append(swir1_entry)

            swir2_entry = QgsRasterCalculatorEntry()
            swir2_entry.ref = 'swir2_band'
            swir2_entry.raster = input_raster
            #custom_widget_inputs[2]---{'B11[SWIR1]': 1, 'B12[SWIR2]': 1}
            swir2_entry.bandNumber = custom_widget_inputs[2]['B12[SWIR2]']
            rc_entries.append(swir2_entry)
            
            rc_expression = rc_expressions[nbr_index]
            bbox = input_raster.extent()
            crs = input_raster.crs()
            width = input_raster.width()
            height = input_raster.height()

            calc = QgsRasterCalculator(rc_expression,
                                       output_raster,
                                       'GTiff',
                                       bbox,
                                       crs,
                                       width,
                                       height,
                                       rc_entries)
                                       
            res = calc.processCalculation(feedback)
            feedback.pushInfo(results[res])
            calc = None
            del calc
            rc_entries.clear()

        elif nbr_index == 'NBR+':
            '''
            custom_widget_inputs[2]---
            {'B12[SWIR2]': 10,
            'B2[BLUE]': 1,
            'B3[GREEN]': 2,
            'B8A[NIR]': 8}
            '''
            rc_entries = []
            ###
            blue_entry = QgsRasterCalculatorEntry()
            blue_entry.ref = 'blue_band'
            blue_entry.raster = input_raster
            blue_entry.bandNumber = custom_widget_inputs[2]['B2[BLUE]']
            rc_entries.append(blue_entry)
            
            green_entry = QgsRasterCalculatorEntry()
            green_entry.ref = 'green_band'
            green_entry.raster = input_raster
            green_entry.bandNumber = custom_widget_inputs[2]['B3[GREEN]']
            rc_entries.append(green_entry)
            
            nir_entry = QgsRasterCalculatorEntry()
            nir_entry.ref = 'nir_band'
            nir_entry.raster = input_raster
            nir_entry.bandNumber = custom_widget_inputs[2]['B8A[NIR]']
            rc_entries.append(nir_entry)

            swir2_entry = QgsRasterCalculatorEntry()
            swir2_entry.ref = 'swir2_band'
            swir2_entry.raster = input_raster
            swir2_entry.bandNumber = custom_widget_inputs[2]['B12[SWIR2]']
            rc_entries.append(swir2_entry)
            
            ####
            rc_expression = rc_expressions[nbr_index]
            bbox = input_raster.extent()
            crs = input_raster.crs()
            width = input_raster.width()
            height = input_raster.height()

            calc = QgsRasterCalculator(rc_expression,
                                       output_raster,
                                       'GTiff',
                                       bbox,
                                       crs,
                                       width,
                                       height,
                                       rc_entries)
                                       
            res = calc.processCalculation(feedback)
            feedback.pushInfo(results[res])
            calc = None
            del calc
            rc_entries.clear()
        
        else:
            raise QgsProcessingException('A valid NBR index was not recognized')
        ###################################################################*****
        ###Rename output layer###
        if context.willLoadLayerOnCompletion(output_raster):
            details = context.layerToLoadOnCompletionDetails(output_raster)
            l = QgsProcessingUtils.mapLayerFromString(output_raster, context, typeHint=details.layerTypeHint)
            #feedback.pushInfo(l.name())
            if l.name() == 'OUTPUT':
                details.name = f'Calculated {nbr_index}'
                details.forceName = True

        return {'Input params': custom_widget_inputs, 'Output raster': output_raster}
        
###########################WIDGET WRAPPER CLASS#################################
# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.cpw = BurnIndexWidget()
        return self.cpw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.cpw.get_params()
        
###########################CUSTOM WIDGET CLASSES################################
class BurnIndexWidget(QWidget):
    
    def __init__(self):
        super().__init__()
        self.input_layer_widget = InputLayerFileWidget(self)
        self.input_layer_widget.mlcb.setFilters(QgsMapLayerProxyModel.RasterLayer)
        ###########################################
        self.tabwidget = QTabWidget(self)
        #NBR Tab
        self.nbr_tab = QWidget(self)
        self.nbr_b8_lbl = QLabel('Select B8 (NIR) band:', self)
        self.nbr_b8_cb = QgsRasterBandComboBox(self)
        self.nbr_b12_lbl = QLabel('Select B12 (SWIR) band:', self)
        self.nbr_b12_cb = QgsRasterBandComboBox(self)
        #
        self.nbr_layout = QGridLayout(self)
        self.nbr_layout.addWidget(self.nbr_b8_lbl, 0, 0, 1, 1, Qt.AlignCenter)
        self.nbr_layout.addWidget(self.nbr_b8_cb, 0, 1, 1, 5)
        self.nbr_layout.addWidget(self.nbr_b12_lbl, 1, 0, 1, 1, Qt.AlignCenter)
        self.nbr_layout.addWidget(self.nbr_b12_cb, 1, 1, 1, 5)
        self.nbr_tab.setLayout(self.nbr_layout)
        #NBR_2 Tab
        self.nbr2_tab = QWidget(self)
        self.nbr2_b8A_lbl = QLabel('Select B8A (NIR) band:', self)
        self.nbr2_b8A_cb = QgsRasterBandComboBox(self)
        self.nbr2_b12_lbl = QLabel('Select B12 (SWIR) band:', self)
        self.nbr2_b12_cb = QgsRasterBandComboBox(self)
        #
        self.nbr2_layout = QGridLayout(self)
        self.nbr2_layout.addWidget(self.nbr2_b8A_lbl, 0, 0, 1, 1, Qt.AlignCenter)
        self.nbr2_layout.addWidget(self.nbr2_b8A_cb, 0, 1, 1, 5)
        self.nbr2_layout.addWidget(self.nbr2_b12_lbl, 1, 0, 1, 1, Qt.AlignCenter)
        self.nbr2_layout.addWidget(self.nbr2_b12_cb, 1, 1, 1, 5)
        self.nbr2_tab.setLayout(self.nbr2_layout)
        #NBR-SWIR Tab
        self.nbrswir_tab = QWidget(self)
        self.nbrswir_b11_lbl = QLabel('Select B11 (SWIR1) band:', self)
        self.nbrswir_b11_cb = QgsRasterBandComboBox(self)
        self.nbrswir_b12_lbl = QLabel('Select B12 (SWIR2) band:', self)
        self.nbrswir_b12_cb = QgsRasterBandComboBox(self)
        #
        self.nbrswir_layout = QGridLayout(self)
        self.nbrswir_layout.addWidget(self.nbrswir_b11_lbl, 0, 0, 1, 1, Qt.AlignCenter)
        self.nbrswir_layout.addWidget(self.nbrswir_b11_cb, 0, 1, 1, 5)
        self.nbrswir_layout.addWidget(self.nbrswir_b12_lbl, 1, 0, 1, 1, Qt.AlignCenter)
        self.nbrswir_layout.addWidget(self.nbrswir_b12_cb, 1, 1, 1, 5)
        self.nbrswir_tab.setLayout(self.nbrswir_layout)
        ###########################################
        #NBR+ Tab
        self.nbrplus_tab = QWidget(self)
        self.nbrplus_b2_lbl = QLabel('Select B2 (BLUE) band:', self)
        self.nbrplus_b2_cb = QgsRasterBandComboBox(self)
        self.nbrplus_b3_lbl = QLabel('Select B3 (GREEN) band:', self)
        self.nbrplus_b3_cb = QgsRasterBandComboBox(self)
        self.nbrplus_b8A_lbl = QLabel('Select B8A (NIR) band:', self)
        self.nbrplus_b8A_cb = QgsRasterBandComboBox(self)
        self.nbrplus_b12_lbl = QLabel('Select B12 (SWIR2) band:', self)
        self.nbrplus_b12_cb = QgsRasterBandComboBox(self)
        #
        self.nbrplus_layout = QGridLayout(self)
        self.nbrplus_layout.addWidget(self.nbrplus_b2_lbl, 0, 0, 1, 1, Qt.AlignCenter)
        self.nbrplus_layout.addWidget(self.nbrplus_b2_cb, 0, 1, 1, 5)
        self.nbrplus_layout.addWidget(self.nbrplus_b3_lbl, 1, 0, 1, 1, Qt.AlignCenter)
        self.nbrplus_layout.addWidget(self.nbrplus_b3_cb, 1, 1, 1, 5)
        self.nbrplus_layout.addWidget(self.nbrplus_b8A_lbl, 2, 0, 1, 1, Qt.AlignCenter)
        self.nbrplus_layout.addWidget(self.nbrplus_b8A_cb, 2, 1, 1, 5)
        self.nbrplus_layout.addWidget(self.nbrplus_b12_lbl, 3, 0, 1, 1, Qt.AlignCenter)
        self.nbrplus_layout.addWidget(self.nbrplus_b12_cb, 3, 1, 1, 5)
        self.nbrplus_tab.setLayout(self.nbrplus_layout)
        
        self.tabwidget.addTab(self.nbr_tab, 'NBR')
        self.tabwidget.addTab(self.nbr2_tab, 'NBR 2')
        self.tabwidget.addTab(self.nbrswir_tab, 'NBR SWIR')
        self.tabwidget.addTab(self.nbrplus_tab, 'NBR+')
        
        self.main_layout = QGridLayout(self)
        self.main_layout.addWidget(self.input_layer_widget, 0, 0, 1, 6)
        self.main_layout.addWidget(self.tabwidget, 1, 0, 1, 6)
        
        self.set_layer(self.input_layer_widget.mlcb.currentLayer())
        self.conn1 = self.input_layer_widget.mlcb.layerChanged.connect(self.set_layer)
        
    def set_layer(self, current_lyr):
        if not current_lyr:
            return()
        if current_lyr.type() == QgsMapLayerType.RasterLayer:
            for cb in self.findChildren(QgsRasterBandComboBox):
                cb.setLayer(current_lyr)
                
    def get_params(self):
        params = [self.input_layer_widget.currentLayer()]
        tab_text = self.tabwidget.tabText(self.tabwidget.currentIndex())
        params.append(tab_text)
        if tab_text == 'NBR':
            bands = {'B8[NIR]': self.nbr_b8_cb.currentBand(),
                    'B12[SWIR]': self.nbr_b12_cb.currentBand()}
        elif tab_text == 'NBR 2':
            bands = {'B8A[NIR]': self.nbr2_b8A_cb.currentBand(),
                    'B12[SWIR]': self.nbr2_b12_cb.currentBand()}
        elif tab_text == 'NBR SWIR':
            bands = {'B11[SWIR1]': self.nbrswir_b11_cb.currentBand(),
                    'B12[SWIR2]': self.nbrswir_b12_cb.currentBand()}
        else:
            #NBR+
            bands = {'B2[BLUE]': self.nbrplus_b2_cb.currentBand(),
                    'B3[GREEN]': self.nbrplus_b3_cb.currentBand(),
                    'B8A[NIR]': self.nbrplus_b8A_cb.currentBand(),
                    'B12[SWIR2]': self.nbrplus_b12_cb.currentBand()}
        params.append(bands)
        
        return params
            
    def closeEvent(self, e):
        #print(self.get_params())
        QObject.disconnect(self.conn1)

#########CUSTOM MAP LAYER WIDGET CLASS####################
class InputLayerFileWidget(QWidget):
    def __init__(self, parent=None):
        self.parent = parent
        QWidget.__init__(self)
        self.lbl = QLabel('Input layer:', self)
        self.mlcb = QgsMapLayerComboBox(self)
        self.file_selection_button = QPushButton("\u2026", self)
        self.file_selection_button.setMaximumWidth(30)
        self.file_selection_button.setToolTip('Select from file')
        #---
        self.h_layout = QHBoxLayout()
        self.h_layout.addWidget(self.lbl, 1)
        self.h_layout.addWidget(self.mlcb, 5)
        self.h_layout.addWidget(self.file_selection_button, 1)
        #---
        self.setLayout(self.h_layout)
        self.file_selection_button.clicked.connect(self.getFile)
        
    def getFile(self):
        file_name = QFileDialog.getOpenFileName(None, 'Select file', '', filter='*.tif; *TIF; *.img')
        if file_name:
            self.mlcb.setAdditionalItems([file_name[0]])
            self.mlcb.setCurrentIndex(self.mlcb.model().rowCount()-1)
            
    def currentLayer(self):
        layer = self.mlcb.currentLayer()
        if layer is not None:
            return layer
        else:
            path = self.mlcb.currentText()
            name = Path(path).stem
            layer = QgsVectorLayer(path, name, 'ogr')
            if layer.isValid():
                return layer
        return None