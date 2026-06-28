from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import (Qt,
                            QCoreApplication,
                            QVariant,
                            QObject)

from qgis.PyQt.QtWidgets import (QWidget,
                                QSizePolicy,
                                QVBoxLayout,
                                QHBoxLayout,
                                QLabel,
                                QTableWidget,
                                QHeaderView,
                                QTableWidgetItem,
                                QComboBox,
                                QLineEdit)
                                
from qgis.PyQt.QtGui import (QIcon)

from qgis.core import (QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsMapLayerProxyModel)
                        
from qgis.gui import QgsMapLayerComboBox

from qgis.utils import iface

from osgeo import gdal
import processing


class SetBandDescriptions(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "setbanddescriptions"
         
    def displayName(self):
        return "Set band descriptions"
 
    def group(self):
        return "Raster General"
 
    def groupId(self):
        return "raster_general"
 
    def shortHelpString(self):
        return "Add band descriptions to an existing raster."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        custom_widget_param = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input Parameters')
        custom_widget_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(custom_widget_param)
        
    def prepareAlgorithm(self, parameters, context, feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        raster_layer = custom_widget_inputs[0]
        band_description_map = custom_widget_inputs[1]
        layer_path = raster_layer.source()
        
        ds = gdal.Open(layer_path, gdal.GA_Update)
        
        for i in range(raster_layer.bandCount()):
            band_name = raster_layer.bandName(i+1)
            rb = ds.GetRasterBand(i+1)
            band_desc = band_description_map[band_name]
            rb.SetDescription(band_desc)
            
        ds = None
        del ds

        raster_layer.dataProvider().reload()
        raster_layer.reload()
        iface.layerTreeView().refreshLayerSymbology(raster_layer.id())
            
        return True
         
    def processAlgorithm(self, parameters, context, feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        raster_layer = custom_widget_inputs[0]
        band_description_map = custom_widget_inputs[1]
        
        return {'Input Layer': raster_layer, 'Band Description Map': band_description_map}

########################PUT WIDGET WRAPPER CLASS HERE###########################
# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.cpw = SetBandDescriptionWidget()
        return self.cpw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.cpw.get_params()
        
###########################CUSTOM WIDGET CLASS################################
class SetBandDescriptionWidget(QWidget):
    
    def __init__(self):
        super().__init__()
        #self.setGeometry(100, 100, 800, 500)
        ###
        self.cb_size_policy = QSizePolicy()
        self.cb_size_policy.setHorizontalPolicy(QSizePolicy.Preferred)
        self.cb_size_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self.cb_size_policy.setHorizontalStretch(1)
        ###
        self.layer_lbl = QLabel('Input raster', self)
        self.layer_cb = QgsMapLayerComboBox(self)
        self.layer_cb.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.layer_cb.setSizePolicy(self.cb_size_policy)
        self.layer_cb_layout = QHBoxLayout()
        self.layer_cb_layout.addWidget(self.layer_lbl)
        self.layer_cb_layout.addWidget(self.layer_cb)
        ###
        self.product_lbl = QLabel('Select product', self)
        self.product_cb = QComboBox(self)
        self.product_cb.addItems(['Sentinel', 'Landsat 5', 'Landsat 7', 'Landsat 8', 'Other'])
        self.product_cb.setSizePolicy(self.cb_size_policy)
        self.product_cb_layout = QHBoxLayout()
        self.product_cb_layout.addWidget(self.product_lbl)
        self.product_cb_layout.addWidget(self.product_cb)
        ######################################################
        #Add table to configure band names & descriptions
        self.band_config_tbl = QTableWidget(self)
        self.band_config_tbl.setColumnCount(2)
        self.band_config_tbl.setColumnWidth(0, 200)
        self.band_config_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.band_config_tbl.setHorizontalHeaderLabels(['Band', 'Description'])
        ############################
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.layer_cb_layout)
        self.main_layout.addLayout(self.product_cb_layout)
        self.main_layout.addWidget(self.band_config_tbl)
        
        ##########################BAND DESCRIPTIONS#############################
        self.S2_bands = ['B01[CA]',
                        'B02[B]',
                        'B03[G]',
                        'B04[R]',
                        'B05[VRE]',
                        'B06[VRE]',
                        'B07[VRE]',
                        'B08[NIR]',
                        'B8A[NIR]',
                        'B09[WV]',
                        'B10[SWIR]',
                        'B11[SWIR]',
                        'B12[SWIR]']

        self.L5_bands = ['B1[B]',
                        'B2[G]',
                        'B3[R]',
                        'B4[NIR]',
                        'B5[SWIR-1]',
                        'B6[TIR]',
                        'B7[SWIR-2]']

        self.L7_bands = ['B1[B]',
                        'B2[G]',
                        'B3[R]',
                        'B4[NIR]',
                        'B5[SWIR]',
                        'B6[TIR]',
                        'B7[MIR]',
                        'B8[PAN]']

        self.L8_bands = ['B1[CA]',
                        'B2[B]',
                        'B3[G]',
                        'B4[R]',
                        'B5[NIR]',
                        'B6[SWIR-1]',
                        'B7[SWIR-2]',
                        'B8[PAN]',
                        'B9[Cirrus]',
                        'B10[TIR-1]',
                        'B11[TIR-2]']
    
        self.product_lookup = {'Sentinel': self.S2_bands,
                                'Landsat 5': self.L5_bands,
                                'Landsat 7': self.L7_bands,
                                'Landsat 8': self.L8_bands,
                                'Other': []}
        self.populate_table(self.layer_cb.currentLayer())
    ############################################################################
        self.layer_cb.layerChanged.connect(self.populate_table)
        self.product_cb.currentIndexChanged.connect(self.populate_table)

    def populate_table(self, arg):
        lyr = self.layer_cb.currentLayer()
        if not lyr:
            return
        #print(lyr.bandCount())
        self.band_config_tbl.setRowCount(lyr.bandCount())
        for i in range(lyr.bandCount()):
            band_name = lyr.bandName(i+1)
            #print(band_name)
            ti = QTableWidgetItem(band_name)
            self.band_config_tbl.setItem(i, 0, ti)
            if self.product_cb.currentText() == 'Other':
                #product_bands = ['Enter band description' for n in range(lyr.bandCount())]
                le = QLineEdit()
                le.setPlaceholderText('Enter band description')
                self.band_config_tbl.setCellWidget(i, 1, le)
            else:
                product_bands = self.product_lookup[self.product_cb.currentText()]
                band_desc_cb = QComboBox()
                band_desc_cb.addItems(product_bands)
                self.band_config_tbl.setCellWidget(i, 1, band_desc_cb)
        
    def get_params(self):
        r_layer = self.layer_cb.currentLayer()
        band_desc_map = {}
        for i in range(self.band_config_tbl.rowCount()):
            band = self.band_config_tbl.item(i, 0).text()
            cell_widget = self.band_config_tbl.cellWidget(i, 1)
            try:
                band_desc = cell_widget.text()
            except AttributeError:
                band_desc = cell_widget.currentText()
            band_desc_map[band] = band_desc
            
        return [r_layer, band_desc_map]#Dictionary inside a list (matrix param)
