#WORKING VERSION May 2026
from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import (Qt,
                            QCoreApplication,
                            QVariant,
                            QObject,
                            QEvent,
                            pyqtSignal)

from qgis.PyQt.QtWidgets import (QWidget,
                                QVBoxLayout,
                                QHBoxLayout,
                                QLabel,
                                QTableWidget,
                                QHeaderView,
                                QAbstractItemView,
                                QTableWidgetItem,
                                QFileDialog,
                                QComboBox,
                                QToolBar,
                                QListWidget,
                                QListWidgetItem,
                                QAction,
                                QDialog,
                                QPushButton,
                                QLineEdit,
                                QFormLayout)
                                
from qgis.PyQt.QtGui import (QFont,
                            QIcon)

from qgis.core import (QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterRasterDestination,
                        QgsProcessingMultiStepFeedback)
                        
from qgis.gui import QgsFileWidget
                        
from datetime import datetime

from osgeo import gdal
import processing

import os

import pathlib

class StackAndClipBands(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
    CLIP_LAYER = 'CLIP_LAYER'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "stackclipbands"
         
    def displayName(self):
        return "Stack and clip bands"
 
    def group(self):
        return "Fire Mapping"
 
    def groupId(self):
        return "fire_mapping"
 
    def shortHelpString(self):
        return "Stack raster bands and add/retain band descriptions."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        custom_widget_param = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input Parameters')
        custom_widget_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(custom_widget_param)
        
        self.addParameter(QgsProcessingParameterFeatureSource(self.CLIP_LAYER, 'Mask layer for clipping', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Output multi-band raster'))
         
    def processAlgorithm(self, parameters, context, model_feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        # example: [['input/raster1/path', 'B02[B]'], ['input/raster2/path', 'B03[G]'], ['input/raster3/path', 'B08[NIR]']]
        input_rasters = [param[0] for param in custom_widget_inputs]#first element of nested lists is input raster path
        band_descriptions = [param[1] for param in custom_widget_inputs]#2nd element of nested lists is band description
        clip_layer = parameters[self.CLIP_LAYER]
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        
        feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        
        build_vrt_params = {'INPUT':input_rasters,
                            'RESOLUTION':1,# Highest
                            'SEPARATE':True,
                            'PROJ_DIFFERENCE':False,
                            'ADD_ALPHA':False,
                            'ASSIGN_CRS':None,
                            'RESAMPLING':2,# Cubic convolution
                            'SRC_NODATA':'',
                            'EXTRA':'',
                            'OUTPUT':'TEMPORARY_OUTPUT'}
        feedback.setCurrentStep(1)
        
        # vrt['OUTPUT'] is a file path to the temporary vrt file X/X/OUTPUT.vrt
        vrt = processing.run("gdal:buildvirtualraster", build_vrt_params, context=context, feedback=feedback, is_child_algorithm = True)
        
        if clip_layer:
            clip_by_rask_params = {'INPUT':vrt['OUTPUT'],
                                    'MASK':clip_layer,
                                    'SOURCE_CRS':None,
                                    'TARGET_CRS':None,
                                    'TARGET_EXTENT':None,
                                    'NODATA':0,
                                    'ALPHA_BAND':False,
                                    'CROP_TO_CUTLINE':True,
                                    'KEEP_RESOLUTION':False,
                                    'SET_RESOLUTION':False,
                                    'X_RESOLUTION':None,
                                    'Y_RESOLUTION':None,
                                    'MULTITHREADING':False,
                                    'OPTIONS':'',
                                    'DATA_TYPE':0,
                                    'EXTRA':'',
                                    'OUTPUT':output_raster}
            feedback.setCurrentStep(2)

            output = processing.run("gdal:cliprasterbymasklayer", clip_by_rask_params, context=context, feedback=feedback, is_child_algorithm = True)
                    
        else:
            translate_params = {'INPUT':vrt['OUTPUT'],
                                'TARGET_CRS':None,
                                'NODATA':None,
                                'COPY_SUBDATASETS':False,
                                'OPTIONS':'',
                                'EXTRA':'',
                                'DATA_TYPE':0,
                                'OUTPUT':output_raster}
            feedback.setCurrentStep(2)

            output = processing.run("gdal:translate", translate_params, context=context, feedback=feedback, is_child_algorithm = True)
        
        ###Set band descriptions
        ds = gdal.Open(output_raster, gdal.GA_Update)
        for i, band_desc in enumerate(band_descriptions):
            rb = ds.GetRasterBand(i+1)
            rb.SetDescription(band_desc)
        del ds
        
        '''
        return {'Input params': custom_widget_inputs,
                'Clip layer': clip_layer,
                'Output': output_raster}
        '''
        return {'OUTPUT': output_raster}
        ##############################

########################PUT WIDGET WRAPPER CLASS HERE###########################
# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.cpw = StackBandsWidget()
        return self.cpw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.cpw.get_params()
###########################CUSTOM WIDGET CLASSES################################

class StackBandsWidget(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.band_widget = BandPanelWidget(self)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.band_widget)
        ######################################################
        ###Add combobox to select product (Sentinel, Landsat 4-8 etc)
        self.product_cb_lbl = QLabel('Select product:', self)
        self.product_cb = QComboBox(self)
        self.product_cb.addItems(['Sentinel', 'Landsat 5', 'Landsat 7', 'Landsat 8', 'Other'])
        #self.product_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ###
        self.product_cb.currentTextChanged.connect(self.product_changed)
        ###
        self.product_cb_layout = QHBoxLayout()
        self.product_cb_layout.addWidget(self.product_cb_lbl, 0, alignment=Qt.AlignRight)
        self.product_cb_layout.addWidget(self.product_cb, 2)
        self.main_layout.addLayout(self.product_cb_layout)
        ######################################################
        #Add table with input file names, band names etc...
        ###Output files config table
        self.band_config_tbl = QTableWidget(self)
        self.band_config_tbl.setColumnCount(3)
        self.band_config_tbl.setColumnWidth(0, 250)
        self.band_config_tbl.setColumnWidth(1, 200)
        self.band_config_tbl.setColumnWidth(2, 50)
        self.band_config_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.band_config_tbl.setHorizontalHeaderLabels(['Input File Name', 'Band Description', ''])
        ############################
        self.main_layout.addWidget(self.band_config_tbl)
        
        self.conn1 = self.band_widget.slw.listChanged.connect(self.band_list_changed)
        
        self.config_icon = QIcon(":images/themes/default/processingAlgorithm.svg")
        
        self.tbl_map = {}
        
        ##########################BAND DESCRIPTIONS#############################
        self.S2_bands = {'B01':'CA',
                        'B02':'B',
                        'B03':'G',
                        'B04':'R',
                        'B05':'VRE',
                        'B06':'VRE',
                        'B07':'VRE',
                        'B08':'NIR',
                        'B8A':'NIR',
                        'B09':'WV',
                        'B10':'SWIR',
                        'B11':'SWIR',
                        'B12':'SWIR'}

        self.L5_bands = {'B1':'B',
                        'B2':'G',
                        'B3':'R',
                        'B4':'NIR',
                        'B5':'SWIR-1',
                        'B6':'TIR',
                        'B7':'SWIR-2'}

        self.L7_bands = {'B1':'B',
                        'B2':'G',
                        'B3':'R',
                        'B4':'NIR',
                        'B5':'SWIR',
                        'B6':'TIR',
                        'B7':'MIR',
                        'B8':'PAN'}

        self.L8_bands = {'B1':'CA',
                        'B2':'B',
                        'B3':'G',
                        'B4':'R',
                        'B5':'NIR',
                        'B6':'SWIR-1',
                        'B7':'SWIR-2',
                        'B8':'PAN',
                        'B9':'Cirrus',
                        'B10':'TIR-1',
                        'B11':'TIR-2'}
    ############################################################################
    def product_changed(self):
        #print('Ping')
        #self.band_list_changed(self.band_widget.slw.file_paths)
        for row_idx in range(self.band_config_tbl.rowCount()):
            tbl_item = self.band_config_tbl.item(row_idx, 0)
            if not tbl_item:
                continue
            fname = tbl_item.text()
            band_name = self.attempt_get_band_details(fname)
            if not band_name:
                self.band_config_tbl.setItem(row_idx, 1, QTableWidgetItem('...'))
                self.tbl_map[fname] = '...'
                return
            band_desc = self.attempt_get_band_desc(self.product_cb.currentText(), band_name)
            if band_desc:
                band_details = f'{band_name}[{band_desc}]'
            else:
                band_details = band_name
            self.band_config_tbl.setItem(row_idx, 1, QTableWidgetItem(band_details))
            self.tbl_map[fname] = band_details
    ############################################################################
    def band_list_changed(self, file_paths):
        #print(self.band_widget.slw.file_paths)
        self.band_config_tbl.setRowCount(len(file_paths))
        for i in range(self.band_config_tbl.rowCount()):
            fpath = file_paths[i]
            fname = pathlib.Path(fpath).stem
            #print(fname)
            self.attempt_set_product(fname)
            ###
            self.band_config_tbl.setItem(i, 0, QTableWidgetItem(fname))
            band_details = self.attempt_get_band_details(fname)
            # If the band details cell has been configured, we keep those details
            # retrieved from the tbl_map dict, to avoid the edited details being
            # overwritten every time the table is reordered or a row is added.
            # TODO: keep track of edits made directly in the cell and update tbl_map.
            ####
            #print(band_details)
            if band_details != '---':
                band_desc = self.attempt_get_band_desc(self.product_cb.currentText(), band_details)
                if band_desc:
                    band_details = f'{band_details}[{band_desc}]'
            ###
            if fname in self.tbl_map.keys() and self.tbl_map[fname] != band_details:
                self.band_config_tbl.setItem(i, 1, QTableWidgetItem(self.tbl_map[fname]))
            else:
                self.band_config_tbl.setItem(i, 1, QTableWidgetItem(band_details))
                self.tbl_map[fname] = band_details
            # Add config button cell widgets
            config_btn = ConfigButton(self.config_icon, f'{i}', self, i)
            config_btn.setToolTip('Configure band details')
            config_btn.configRequested.connect(self.configureBandDetails)
            self.band_config_tbl.setCellWidget(i, 2, config_btn)
            ###
        ###Remove item from tbl_map if it has been removed from band list widget
        tbl_fnames = [self.band_config_tbl.item(i, 0).text() for i in range(self.band_config_tbl.rowCount())]
        items_for_removal = [item for item in self.tbl_map.items() if not item[0] in tbl_fnames]
        for item in items_for_removal:
            self.tbl_map.pop(item[0])
        ###
        #print(self.tbl_map)
        
    def attempt_set_product(self, file_name):
        chunk1 = file_name.split('_')[0]
        if chunk1.startswith('T') or chunk1.startswith('S'):
            self.product_cb.setCurrentText('Sentinel')
        if chunk1.startswith('L'):
            if chunk1[-1]=='5':
                self.product_cb.setCurrentText('Landsat 5')
            if chunk1[-1]=='7':
                self.product_cb.setCurrentText('Landsat 7')
            if chunk1[-1]=='8':
                self.product_cb.setCurrentText('Landsat 8')
            
    def configureBandDetails(self, row_idx):
        #print(row_idx)
        fn = self.band_config_tbl.item(row_idx, 0).text()
        config_dlg = ConfigDialog(fn, self)
        result = config_dlg.exec_()
        if result == QDialog.Accepted:
            #print(config_dlg.chunk_cb.currentText())
            fname = self.band_config_tbl.item(row_idx, 0).text()
            band_name = config_dlg.chunk_cb.currentText()
            if not band_name:
                self.band_config_tbl.setItem(row_idx, 1, QTableWidgetItem('...'))
                self.tbl_map[fname] = '...'
                return
            band_desc = self.attempt_get_band_desc(self.product_cb.currentText(), band_name)
            if band_desc:
                band_details = f'{band_name}[{band_desc}]'
            else:
                band_details = band_name
            self.band_config_tbl.setItem(row_idx, 1, QTableWidgetItem(band_details))
            self.tbl_map[fname] = band_details
            #print(self.tbl_map)
            
    def attempt_get_band_details(self, file_name):
        fn_chunks = file_name.split('_')
        if len(fn_chunks) > 1:
            for fn_chunk in fn_chunks:
                if fn_chunk.startswith('B'):
                    return fn_chunk
        else:
            fn_chunks = file_name.split('-')
        if len(fn_chunks) > 1:
            for fn_chunk in fn_chunks:
                if fn_chunk.startswith('B'):
                    return fn_chunk
        return '---'
        
    def attempt_get_band_desc(self, product, band_name):
        band_list_dict = {'Sentinel': self.S2_bands,
                            'Landsat 5': self.L5_bands,
                            'Landsat 7': self.L7_bands,
                            'Landsat 8': self.L8_bands,
                            'Other': {}}
        band_list = band_list_dict[product]
        if band_list and band_name in band_list.keys():
            return band_list[band_name]
        return None
                
    def closeEvent(self, e):
        QObject.disconnect(self.conn1)
        
    def get_params(self):
        param_matrix = []
        file_list = self.band_widget.slw.file_paths
        for i, fp in enumerate(file_list):
            band_desc = self.band_config_tbl.item(i, 1).text()
            param_matrix.append([fp, band_desc])
        return param_matrix
        
        
#########################CONFIG BUTTON SUBCLASS#################################
class ConfigButton(QPushButton):
    configRequested = pyqtSignal(int)
    def __init__(self, icon, txt, parent, row_idx):
        self.icon = icon
        self.txt = txt
        self.parent = parent
        self.row_idx = row_idx
        super().__init__(self.icon, self.txt, self.parent)
        
    def mouseReleaseEvent(self, e):
        self.configRequested.emit(self.row_idx)
        
#############################CONFIG DIALOG######################################
class ConfigDialog(QDialog):
    def __init__(self, file_name, parent=None):
        self.parent = parent
        self.file_name = file_name
        super().__init__(self.parent)
        self.setWindowTitle('Configure Band Details')
        self.split_char_le = QLineEdit(self)
        self.split_char_le.setText('_')# Start with an underscore
        self.chunk_cb = QComboBox(self)
        self.layout = QFormLayout(self)
        self.layout.addRow('Enter split character', self.split_char_le)
        self.layout.addRow('Select band details', self.chunk_cb)
        ###
        self.close_btn = QPushButton('Cancel', self)
        self.ok_btn = QPushButton('OK', self)
        self.ok_btn.clicked.connect(lambda: self.accept())
        self.close_btn.clicked.connect(lambda: self.reject())
        self.btn_layout = QHBoxLayout()
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.close_btn)
        self.btn_layout.addWidget(self.ok_btn)
        self.layout.addRow(self.btn_layout)
        ###
        self.split_char_le.textChanged.connect(self.populate_cb)
        self.populate_cb()
        
    def populate_cb(self):
        self.chunk_cb.clear()
        split_char = self.split_char_le.text()
        if not split_char:
            return
        split_chunks = self.file_name.split(split_char)
        if not len(split_chunks)>1:
            return
        self.chunk_cb.addItems(split_chunks)
        for n in split_chunks:
            if n.startswith('B'):
                self.chunk_cb.setCurrentText(n)
        
        
################################################################################
class BandPanelWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        #############
        self.top_layout = QHBoxLayout()
        self.scene_lbl = QLabel('Input bands for stacking', self)
        self.scene_lbl.setFont(QFont('Arial', 12))
        self.top_layout.addWidget(self.scene_lbl)
        #############
        self.tb = QToolBar(self)
        #self.tb.setMaximumHeight(30)
        self.tb.setStyleSheet("QToolBar {icon-size: 20px;}")
        self.add_action = QAction(QIcon(":images/themes/default/symbologyAdd.svg"), '', self)
        self.add_action.setToolTip('Add files')
        self.remove_action = QAction(QIcon(":images/themes/default/symbologyRemove.svg"), '', self)
        self.remove_action.setToolTip('Remove selected files')
        self.select_action = QAction(QIcon(":images/themes/default/mActionSelectAllTree.svg"), '', self)
        self.select_action.setToolTip('Select all')
        self.deselect_action = QAction(QIcon(":images/themes/default/mActionDeselectAllTree.svg"), '', self)
        self.deselect_action.setToolTip('Deselect all')
        self.clear_action = QAction(QIcon(":images/themes/default/console/iconClearConsole.svg"), '', self)
        self.clear_action.setToolTip('Clear all')
        self.sort_asc_action = QAction(QIcon(":images/themes/default/mActionArrowUp.svg"), '', self)
        self.sort_asc_action.setToolTip('Sort ascending')
        self.sort_desc_action = QAction(QIcon(":images/themes/default/mActionArrowDown.svg"), '', self)
        self.sort_desc_action.setToolTip('Sort descending')
        #
        self.tb.addAction(self.add_action)
        self.tb.addAction(self.remove_action)
        self.tb.addAction(self.select_action)
        self.tb.addAction(self.deselect_action)
        self.tb.addAction(self.clear_action)
        self.tb.addAction(self.sort_asc_action)
        self.tb.addAction(self.sort_desc_action)
        #
        self.top_layout.addWidget(self.tb)
        self.top_layout.addStretch()
        #############
        self.slw = SceneListWidget(self)
        self.panel_layout = QVBoxLayout(self)
        self.panel_layout.addLayout(self.top_layout)
        self.panel_layout.addWidget(self.slw)


class SceneListWidget(QListWidget):
    listChanged = pyqtSignal(list)
    def __init__(self, parent):
        self.parent = parent
        super().__init__(self.parent)
        
        self.file_paths = []
        
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        ###SORTING AND SELECTION######
        #*Sorting is not enabled as we want to allow reordering via internal drag n drop...
        #.. and implement our own sorting logic.
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        ########Signal/slots (passed from actions owned by parent QWidget)######
        self.parent.add_action.triggered.connect(self.addFile)
        self.parent.remove_action.triggered.connect(self.removeFile)
        self.parent.select_action.triggered.connect(self.selectAllItems)
        self.parent.deselect_action.triggered.connect(self.deselectAllItems)
        self.parent.clear_action.triggered.connect(self.clearListWidget)
        self.parent.sort_asc_action.triggered.connect(self.sortListAscending)
        self.parent.sort_desc_action.triggered.connect(self.sortListDescending)
        
        self.installEventFilter(self)
    
    def dragEnterEvent(self, event):
        event.accept()
        return QListWidget.dragEnterEvent(self, event)

    def dragMoveEvent(self, event):
        event.accept()
        return QListWidget.dragMoveEvent(self, event)
    
    def dropEvent(self, event):
        event.accept()
        if event.mimeData():
            #print(event.mimeData().text().split('\n'))
            path_strings = event.mimeData().text().split('\n')
            for file_path in path_strings:
                if not file_path:
                    continue
                uri = file_path.split('file:///')[1]
                uri_item = QListWidgetItem(uri)
                self.addItem(uri_item)
        self.file_paths.clear()
        for i in range(len(self)):
            self.file_paths.append(self.item(i).text())
        self.listChanged.emit(self.file_paths)
        return QListWidget.dropEvent(self, event)
    
    #########################################################################################
    def eventFilter(self, obj, event):
        #print(event.type() == QEvent.ChildRemoved)#71
        #print(event.type())
        #if event.type() in (QEvent.ChildRemoved, QEvent.ChildAdded):
        if event.type() == QEvent.ChildRemoved:
            #print(event.type())
            self.model_rows_moved()
        return super().eventFilter(obj, event)
    
    def model_rows_moved(self):
        self.file_paths.clear()
        for i in range(len(self)):
            self.file_paths.append(self.item(i).text())
        self.listChanged.emit(self.file_paths)
    ###########################################################################################
            
    def addFile(self):
        get_paths = QFileDialog.getOpenFileNames(self, 'Add rasters', '', 'Rasters(*.tif *.tiff *.img *.jp2)')
        file_paths = get_paths[0]# Return value is a tuple- (['List of file paths'], 'The filter string')
        if file_paths:
            for fp in file_paths:
                self.file_paths.append(fp)
        self.populateListWidget()
        
    def removeFile(self):
        selected_items = self.selectedItems()
        for i in selected_items:
            self.file_paths.remove(i.text())
        self.populateListWidget()
        
    def populateListWidget(self):
        self.clear()
        for i, fp in enumerate(self.file_paths):
            lwi = QListWidgetItem(fp)
            self.insertItem(i, lwi)
        self.listChanged.emit(self.file_paths)
        
    def selectAllItems(self):
        self.selectAll()
            
    def deselectAllItems(self):
        self.clearSelection()
            
    def clearListWidget(self):
        self.file_paths.clear()
        self.clear()
        self.listChanged.emit(self.file_paths)
        
    def sortListAscending(self):
        sorted_filepaths = sorted(self.file_paths)
        self.file_paths.clear()
        self.file_paths = [p for p in sorted_filepaths]
        self.populateListWidget()
        
    def sortListDescending(self):
        sorted_filepaths = sorted(self.file_paths, reverse=True)
        self.file_paths.clear()
        self.file_paths = [p for p in sorted_filepaths]
        self.populateListWidget()
################################################################################