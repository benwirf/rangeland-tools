#WORKING VERSION May 2026
from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import QCoreApplication, QVariant, QObject, pyqtSignal

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
                                QAction)
                                
from qgis.PyQt.QtGui import (QFont,
                            QBrush,
                            QColor,
                            QIcon)

from qgis.core import (QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingMultiStepFeedback)
                        
from qgis.gui import QgsFileWidget
                        
from datetime import datetime

import processing

import os
                       
class BatchMergeAndClipScenes(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
    CLIP_LAYER = 'CLIP_LAYER'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "mergeclipscenes"
         
    def displayName(self):
        return "Merge and clip scenes"
 
    def group(self):
        return "Fire Mapping"
 
    def groupId(self):
        return "fire_mapping"
 
    def shortHelpString(self):
        return "Batch merge scene band rasters of Sentinel 2 or Landsat products."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def checkParameterValues(self, parameters, context):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        if (not custom_widget_inputs[2]) or (not os.path.exists(custom_widget_inputs[2])):
            return False, 'Select a valid output folder.'
        if (len(custom_widget_inputs[0]) == 0 and len(custom_widget_inputs[1]) == 0):
            return False, 'Missing parameter input rasters.'
        if not (len(custom_widget_inputs[0]) == len(custom_widget_inputs[1]) == len(custom_widget_inputs[3])):
            return False, 'Incorrect parameter for input or output rasters.'
        return super().checkParameterValues(parameters, context)
   
    def initAlgorithm(self, config=None):
        custom_widget_param = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input Parameters')
        custom_widget_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(custom_widget_param)
        
        self.addParameter(QgsProcessingParameterFeatureSource(self.CLIP_LAYER, 'Mask layer for clipping', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None, optional=True))
         
    def processAlgorithm(self, parameters, context, model_feedback):
        custom_widget_inputs = self.parameterAsMatrix(parameters, 'INPUT_PARAMS', context)
        scene_1_input_paths = custom_widget_inputs[0]
        scene_2_input_paths = custom_widget_inputs[1]
        output_paths = custom_widget_inputs[3]
        
        clip_layer = parameters[self.CLIP_LAYER]
        ##############################
        '''
        return {'INPUTS_1':scene_1_input_paths,
                'INPUTS_2':scene_2_input_paths,
                'OUTPUT_PATHS':output_paths}
        '''
        #########################Set up multi-step feedback
        steps = (len(output_paths)*2)+1
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        step = 1
        ###################################################
        #feedback.pushInfo(repr(clip_layer))
        
        for i in range(len(output_paths)):
            if feedback.isCanceled():
                break
            inputs = [scene_1_input_paths[i], scene_2_input_paths[i]]
            vrt_params = {'INPUT':inputs,
                            'RESOLUTION':1,# Highest
                            'SEPARATE':False,
                            'PROJ_DIFFERENCE':False,
                            'ADD_ALPHA':False,
                            'ASSIGN_CRS':None,
                            'RESAMPLING':2,# Cubic convolution
                            'SRC_NODATA':'',
                            'EXTRA':'',
                            'OUTPUT':'TEMPORARY_OUTPUT'}
            
            feedback.setCurrentStep(step)
            step+=1
            vrt = processing.run("gdal:buildvirtualraster", vrt_params)
            # vrt['OUTPUT'] is a file path to the temporary vrt file X/X/OUTPUT.vrt
            if clip_layer:
                clip_params = {'INPUT':vrt['OUTPUT'],
                                'MASK':clip_layer,
                                'SOURCE_CRS':None,
                                'TARGET_CRS':None,
                                'TARGET_EXTENT':None,
                                'NODATA':None,
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
                                'OUTPUT':output_paths[i]}

                feedback.setCurrentStep(step)
                step+=1
                processing.run("gdal:cliprasterbymasklayer", clip_params)
                
            else:
                translate_params = {'INPUT':vrt['OUTPUT'],
                                    'TARGET_CRS':None,
                                    'NODATA':None,
                                    'COPY_SUBDATASETS':False,
                                    'OPTIONS':'',
                                    'EXTRA':'',
                                    'DATA_TYPE':0,
                                    'OUTPUT':output_paths[i]}
                                    
                feedback.setCurrentStep(step)
                step+=1
                processing.run("gdal:translate", translate_params)
 
        return {'OUTPUT_PATHS': output_paths}
        

# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.cpw = MergeScenesWidget()
        return self.cpw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.cpw.getIOPaths()
        
        
class MergeScenesWidget(QWidget):
    
    def __init__(self):
        super().__init__()
        
        #Scenes panel
        self.scene_1_widget = ScenePanelWidget(self, 1)
        self.scene_1_layout = QVBoxLayout()
        self.scene_1_layout.addWidget(self.scene_1_widget)
        #
        self.scene_2_widget = ScenePanelWidget(self, 2)
        self.scene_2_layout = QVBoxLayout()
        self.scene_2_layout.addWidget(self.scene_2_widget)
        
        self.scenes_layout = QHBoxLayout()
        self.scenes_layout.addLayout(self.scene_1_layout)
        self.scenes_layout.addLayout(self.scene_2_layout)
        
        self.outdir_layout = QHBoxLayout()
        self.outdir_lbl = QLabel('Output folder', self)
        self.outdir_widget = QgsFileWidget(self)
        self.outdir_widget.setStorageMode(QgsFileWidget.GetDirectory)
        self.outdir_layout.addWidget(self.outdir_lbl)
        self.outdir_layout.addWidget(self.outdir_widget)
        
        ###Output files config table
        self.output_config_tbl = QTableWidget(self)
        self.output_config_tbl.setColumnCount(4)
        self.output_config_tbl.setColumnWidth(1, 150)
        self.output_config_tbl.setColumnWidth(2, 100)
        self.output_config_tbl.setColumnWidth(3, 70)
        self.output_config_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.output_config_tbl.setHorizontalHeaderLabels(['Output Folder', 'Acquisition Date', 'Band', 'Extension'])

        ############################
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.scenes_layout)
        self.main_layout.addLayout(self.outdir_layout)
        self.main_layout.addWidget(self.output_config_tbl)
        
        ##############################
        self.conn1 = self.scene_1_widget.slw.listChanged.connect(self.scene_lists_changed)
        self.conn2 = self.scene_2_widget.slw.listChanged.connect(self.scene_lists_changed)
        self.conn3 = self.outdir_widget.fileChanged.connect(self.populate_tbl)
        #self.conn4 = self.outdir_widget.lineEdit().cleared.connect(self.populate_tbl)
        
        self.months = ['Jan', 'Feb', 'Mar', 'April', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec']
        
    def scene_lists_changed(self):
        scene_1_count = len(self.scene_1_widget.slw)
        scene_2_count = len(self.scene_2_widget.slw)
        self.output_config_tbl.setRowCount(min([scene_1_count, scene_2_count]))
        self.populate_tbl()
        #if scene_1_count != scene_2_count:
        
    def parseSentinelFile(self, file_name):
        #scene_file_name = file_name.split('.')[0]
        file_name_split = file_name.split('_')
        if not file_name_split or len(file_name_split) < 2:
            return 'Invalid', 'Invalid'
        if not file_name_split[1].split('T'):
            return 'Invalid', 'Invalid'
        dt_string = file_name_split[1].split('T')[0]
        try:
            scene_dt = datetime.strptime(dt_string, '%Y%m%d').date()#.month
        except ValueError:
            return 'Invalid', 'Invalid'
        scene_mnth = self.months[scene_dt.month-1]
        scene_day = scene_dt.day
        scene_year = scene_dt.year
        scene_acq_date = f'{scene_mnth}_{scene_day}_{scene_year}'
        #scene_resolution = file_name_split[3]
        #scene_band = f'{file_name_split[2]}_{scene_resolution}'
        scene_band = file_name_split[2]

        return scene_acq_date, scene_band
            
    def parseLandsatFile(self, file_name):
        #scene_file_name = file_name.split('.')[0]
        file_name_split = file_name.split('_')
        if not file_name_split or len(file_name_split) < 4:
            return 'Invalid', 'Invalid'
        dt_string = file_name_split[3]
        try:
            scene_dt = datetime.strptime(dt_string, '%Y%m%d').date()
        except ValueError:
            return 'Invalid', 'Invalid'
        scene_mnth = self.months[scene_dt.month-1]
        scene_day = scene_dt.day
        scene_year = scene_dt.year
        scene_acq_date = f'{scene_mnth}_{scene_day}_{scene_year}'
        scene_band = file_name_split[len(file_name_split)-1]
        return scene_acq_date, scene_band
        
    def populate_tbl(self):
        #Output folder column
        for i in range(self.output_config_tbl.rowCount()):
            ti = QTableWidgetItem(self.outdir_widget.filePath())
            self.output_config_tbl.setItem(i, 0, ti)
            self.output_config_tbl.resizeColumnToContents(0)
        
        for i in range(self.output_config_tbl.rowCount()):
            #Acquisition Date column
            # Scene 1
            scene_1_item = self.scene_1_widget.slw.item(i)
            s1_file_name = scene_1_item.text().split('/')[-1].split('.')[0]
            if s1_file_name.startswith('T'):# Sentinel
                (s1_acquisition_date, s1_band_info) = self.parseSentinelFile(s1_file_name)
            elif s1_file_name.startswith('L'):# Landsat
                (s1_acquisition_date, s1_band_info) = self.parseLandsatFile(s1_file_name)
            else:
                (s1_acquisition_date, s1_band_info) = ('Invalid', 'Invalid')
                
            # Scene 2
            scene_2_item = self.scene_2_widget.slw.item(i)
            s2_file_name = scene_2_item.text().split('/')[-1].split('.')[0]
            if s2_file_name.startswith('T'):# Sentinel
                (s2_acquisition_date, s2_band_info) = self.parseSentinelFile(s2_file_name)
            elif s2_file_name.startswith('L'):# Landsat
                (s2_acquisition_date, s2_band_info) = self.parseLandsatFile(s2_file_name)
            else:
                (s2_acquisition_date, s2_band_info) = ('Invalid', 'Invalid')
            ####################################################
            if s1_acquisition_date == s2_acquisition_date:
                ti = QTableWidgetItem(s1_acquisition_date)
                ti.setForeground(QBrush(QColor('black')))
                self.output_config_tbl.setItem(i, 1, ti)
            else:
                ti = QTableWidgetItem('Date mismatch')
                ti.setForeground(QBrush(QColor('red')))
                self.output_config_tbl.setItem(i, 1, ti)
            ###
            if s1_band_info == s2_band_info:
                ti = QTableWidgetItem(s1_band_info)
                ti.setForeground(QBrush(QColor('black')))
                self.output_config_tbl.setItem(i, 2, ti)
            else:
                ti = QTableWidgetItem('Band mismatch')
                ti.setForeground(QBrush(QColor('red')))
                self.output_config_tbl.setItem(i, 2, ti)
            
        #File extension column
        for i in range(self.output_config_tbl.rowCount()):
            cell_cb = QComboBox(self.output_config_tbl)
            cell_cb.addItems(['.tif', '.img', '.jp2'])
            self.output_config_tbl.setCellWidget(i, 3, cell_cb)
            
    def closeEvent(self, e):
        QObject.disconnect(self.conn1)
        QObject.disconnect(self.conn2)
        QObject.disconnect(self.conn3)
        #QObject.disconnect(self.conn4)
        
    def getIOPaths(self):
        scene_1_input_paths = []
        for i in range(self.scene_1_widget.slw.count()):
            scene_1_input_paths.append(self.scene_1_widget.slw.item(i).text())
        scene_2_input_paths = []
        for i in range(self.scene_2_widget.slw.count()):
            scene_2_input_paths.append(self.scene_2_widget.slw.item(i).text())
        output_paths = []
        dest_dir = self.outdir_widget.filePath()
        for i in range(self.output_config_tbl.rowCount()):
            dest_folder = self.output_config_tbl.item(i, 0).text()
            acq_date = self.output_config_tbl.item(i, 1).text()
            band_info = self.output_config_tbl.item(i, 2).text()
            if (acq_date in ['Invalid', 'Date mismatch']) or (band_info in ['Invalid', 'Band mismatch']):
                continue
            ouput_ext = self.output_config_tbl.cellWidget(i, 3).currentText()
            output_file = f'{acq_date}_{band_info}{ouput_ext}'
            output_path = os.path.join(dest_folder, output_file)
            output_paths.append(output_path)
        return [scene_1_input_paths, scene_2_input_paths, dest_dir, output_paths]

########################################################################
class ScenePanelWidget(QWidget):
    def __init__(self, parent, scene_no=1):
        super().__init__()
        self.parent = parent
        self.scene_no = scene_no
        #############
        self.top_layout = QHBoxLayout()
        self.scene_lbl = QLabel(f'Scene {self.scene_no}', self)
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
        #
        self.tb.addAction(self.add_action)
        self.tb.addAction(self.remove_action)
        self.tb.addAction(self.select_action)
        self.tb.addAction(self.deselect_action)
        self.tb.addAction(self.clear_action)
        #
        self.top_layout.addWidget(self.tb)
        self.top_layout.addStretch()
        #############
        self.slw = SceneListWidget(self)
        self.panel_layout = QVBoxLayout(self)
        self.panel_layout.addLayout(self.top_layout)
        self.panel_layout.addWidget(self.slw)

        ########Signal/slots######
        self.add_action.triggered.connect(lambda: self.slw.addFile())
        self.remove_action.triggered.connect(lambda: self.slw.removeFile())
        self.select_action.triggered.connect(lambda: self.slw.selectAllItems())
        self.deselect_action.triggered.connect(lambda: self.slw.deselectAllItems())
        self.clear_action.triggered.connect(lambda: self.slw.clearListWidget())


class SceneListWidget(QListWidget):
    listChanged = pyqtSignal()
    def __init__(self, parent):
        super().__init__()
        
        self.file_paths = []
        
        self.setAcceptDrops(True)
        ###SORTING AND SELECTION######
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
    
    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()
    
    def dropEvent(self, event):
        if event.mimeData():
            event.accept()
            #print(event.mimeData().text().split('\n'))
            path_strings = event.mimeData().text().split('\n')
            for file_path in path_strings:
                if not file_path:
                    continue
                #print(file_path)
                uri = file_path.split('file:///')[1]
                uri_item = QListWidgetItem(uri)
                self.addItem(uri_item)
                self.file_paths.append(uri)
            self.listChanged.emit()
            
    def addFile(self):
        get_paths = QFileDialog.getOpenFileNames(self, 'Add rasters', '', 'Rasters(*.tif *.tiff *.img *.jp2)')
        file_paths = get_paths[0]# Return value is a tuple- (['List of file paths'], 'The filter string')
        if file_paths:
            for fp in file_paths:
                self.file_paths.append(fp)
        self.populateListWidget()
        
    def removeFile(self):
        #print(self.file_paths)
        selected_items = self.selectedItems()
        for i in selected_items:
            #print(i.text())
            self.file_paths.remove(i.text())
        self.populateListWidget()
        
    def populateListWidget(self):
        self.clear()
        #print(self.file_paths)
        for i, fp in enumerate(self.file_paths):
            lwi = QListWidgetItem(fp)
            self.insertItem(i, lwi)
        #self.sortItems()
        self.listChanged.emit()
        
    def selectAllItems(self):
        self.selectAll()
            
    def deselectAllItems(self):
        self.clearSelection()
            
    def clearListWidget(self):
        self.file_paths.clear()
        self.clear()
        self.listChanged.emit()
########################################################################
 