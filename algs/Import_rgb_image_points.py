from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import (QCoreApplication,
                                QVariant,
                                Qt,
                                QEvent,
                                pyqtSignal)
                                
from qgis.PyQt.QtWidgets import (QLabel,
                                QWidget,
                                QHBoxLayout,
                                QListWidget,
                                QListWidgetItem,
                                QAbstractItemView,
                                QPushButton,
                                QVBoxLayout,
                                QFileDialog,
                                QToolButton,
                                QComboBox,
                                QListView,
                                QTreeView,
                                QFileSystemModel)
                                
from qgis.PyQt.QtGui import QIcon
                                
from qgis.core import (QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterFeatureSink,
                        QgsFields,
                        QgsField,
                        QgsWkbTypes,
                        QgsCoordinateReferenceSystem,
                        QgsFeature,
                        QgsPoint,
                        QgsGeometry,
                        QgsFeatureSink)
                        
from PIL import Image
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS

import os
                       
class Import_RGB_Image_Points(QgsProcessingAlgorithm):
    INPUT_DIRS = 'INPUT_DIRS'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "importrgbimagepoints"
         
    def displayName(self):
        return "Import RGB Image Points"
 
    def group(self):
        return "Drone Mapping"
 
    def groupId(self):
        return "dronemapping"
 
    def shortHelpString(self):
        return "Import raw RGB image locations from multiple DJI folders to a \
        point layer using exif information stored in jpg images."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        input_dirs = QgsProcessingParameterMatrix(self.INPUT_DIRS, 'Input directories')
        input_dirs.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(input_dirs)
        
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'Output layer', QgsProcessing.TypeVectorPoint))
        

    def processAlgorithm(self, parameters, context, feedback):
        # Retrieve the list of parameters returned by the custom widget wrapper
        input_dirs_list = self.parameterAsMatrix(parameters, self.INPUT_DIRS, context)

        fields = QgsFields()

        fields_to_add = [QgsField('Name', QVariant.String),
                        QgsField('Time', QVariant.String),
                        QgsField('Latitude', QVariant.Double, len=12, prec=8),
                        QgsField('Longitude', QVariant.Double, len=12, prec=8),
                        QgsField('Altitude', QVariant.Double, len=7, prec=3)]
                        
        for fld in fields_to_add:
            fields.append(fld)
        
        (sink, dest_id) = self.parameterAsSink(parameters,
                                                self.OUTPUT,
                                                context,
                                                fields,
                                                QgsWkbTypes.Point,
                                                QgsCoordinateReferenceSystem('epsg:4326'))
        ###################################################################
        for folder_path in input_dirs_list:
            folder_files = [file for file in os.scandir(folder_path)]
            rgb_images = []
            for f in folder_files:
                if len(f.name.split('.')) < 2:
                    continue
                if f.name.split('.')[1] == 'JPG':
                    rgb_images.append(f)

            for image_file in rgb_images:
                img_name = image_file.name.split('.')[0]
                img_path = image_file.path
                img=Image.open(img_path)
                info_tup = self.get_exif_gps_info(img)
                date_time = info_tup[0]
                lat = info_tup[1]
                lon = info_tup[2]
                alt = info_tup[3]
                
                feat = QgsFeature(fields)
                pt = QgsPoint()
                pt.setX(lon)
                pt.setY(lat)
                pt.addZValue(alt)
                geom = QgsGeometry(pt)
                feat.setGeometry(geom)
                feat.setAttributes([img_name, date_time, str(lat), str(lon), str(alt)])
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
        ###################################################################

        return {self.INPUT_DIRS: input_dirs_list, self.OUTPUT: dest_id}
        
    def get_exif_gps_info(self, image_file):
        exif_table={}
        
        for k, v in image_file._getexif().items():
            tag=TAGS.get(k)
            exif_table[tag]=v
            
        dt = exif_table['DateTime']

        gps_info={}

        for k, v in exif_table['GPSInfo'].items():
            geo_tag=GPSTAGS.get(k)
            gps_info[geo_tag]=v

        lat_dms = gps_info['GPSLatitude']
        lon_dms = gps_info['GPSLongitude']
        gps_alt = gps_info['GPSAltitude']
        
        lat_dd = round(float((lat_dms[0])+(lat_dms[1]/60)+(lat_dms[2]/3600)), 8)
        lon_dd = round(float((lon_dms[0])+(lon_dms[1]/60)+(lon_dms[2]/3600)), 8)
        
        return (dt, -lat_dd, lon_dd, gps_alt)

# Widget Wrapper class
class CustomParametersWidget(WidgetWrapper):

    def createWidget(self):
        self.mdw = MultiDirWidget()
        return self.mdw
        
    def value(self):
        # This method gets the parameter values and returns them in a list...
        # which will be retrieved and parsed in the processAlgorithm() method
        return self.mdw.dirPaths()
        
# Custom Widget class
class MultiDirWidget(QWidget):
    def __init__(self):
        super(MultiDirWidget, self).__init__()
        #self.setMinimumWidth(600)
        #self.setMinimumHeight(500)
        self.dir_paths = []
        self.main_layout = QHBoxLayout(self)
        self.list_widget = QListWidget(self)
        ###SORTING AND SELECTION######
        self.list_widget.setSortingEnabled(True)
        self.list_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        ##################################################
        self.add_multi_btn = QPushButton(QIcon(":images/themes/default/mActionFileOpen.svg"), '', self)
        self.add_multi_btn.setToolTip('Add multiple directories')
        self.add_btn = QPushButton(QIcon(":images/themes/default/symbologyAdd.svg"), '', self)
        self.add_btn.setToolTip('Add directory')
        self.remove_btn = QPushButton(QIcon(":images/themes/default/symbologyRemove.svg"), '', self)
        self.remove_btn.setToolTip('Remove selected')
        self.select_btn = QPushButton(QIcon(":images/themes/default/mActionSelectAllTree.svg"), '', self)
        self.select_btn.setToolTip('Select all')
        self.deselect_btn = QPushButton(QIcon(":images/themes/default/mActionDeselectAllTree.svg"), '', self)
        self.deselect_btn.setToolTip('Deselect all')
        self.clear_btn = QPushButton(QIcon(":images/themes/default/console/iconClearConsole.svg"), '', self)
        self.clear_btn.setToolTip('Clear all')
        self.main_layout.addWidget(self.list_widget)
        self.btn_layout = QVBoxLayout(self)
        self.btn_layout.addWidget(self.add_multi_btn)
        self.btn_layout.addWidget(self.add_btn)
        self.btn_layout.addWidget(self.remove_btn)
        self.btn_layout.addWidget(self.select_btn)
        self.btn_layout.addWidget(self.deselect_btn)
        self.btn_layout.addWidget(self.clear_btn)
        self.btn_layout.addStretch()
        self.main_layout.addLayout(self.btn_layout)
        
        self.add_multi_btn.clicked.connect(self.addMultipleDirectories)
        self.add_btn.clicked.connect(self.addDirectory)
        self.remove_btn.clicked.connect(self.removeDirectory)
        self.select_btn.clicked.connect(self.selectAllItems)
        self.deselect_btn.clicked.connect(self.deselectAllItems)
        self.clear_btn.clicked.connect(self.clearListWidget)
        
        self.dlg = SelectDirectoriesDialog()
        self.dlg.directories_selected.connect(self.directoriesSelected)
        
    def addDirectory(self):
        dir_path = QFileDialog.getExistingDirectory()
        if dir_path:
            self.dir_paths.append(dir_path)
        self.populateListWidget()
    
    def addMultipleDirectories(self):
        self.dlg.show()
        
    def directoriesSelected(self, dir_paths):
        for dir_path in dir_paths:
            self.dir_paths.append(dir_path)
        self.populateListWidget()
        
    def removeDirectory(self):
        selected_items = self.list_widget.selectedItems()
        for i in selected_items:
            self.dir_paths.remove(i.text())
        self.populateListWidget()
        
    def populateListWidget(self):
        self.list_widget.clear()
        for fp in self.dir_paths:
            lwi = QListWidgetItem(fp)
            self.list_widget.addItem(lwi)
        self.list_widget.sortItems()
        
    def selectAllItems(self):
        self.list_widget.selectAll()
            
    def deselectAllItems(self):
        self.list_widget.clearSelection()
            
    def clearListWidget(self):
        self.dir_paths.clear()
        self.list_widget.clear()
        
    def dirPaths(self):
        return self.dir_paths

###--------------------------------------------------------------------------###

class SelectDirectoriesDialog(QFileDialog):
    directories_selected = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.DirectoryOnly)
        ##############Remove the New Folder Button#############
        for a in self.findChildren((QToolButton)):
            if a.toolTip() == 'Create New Folder':
                a.setVisible(False)
        #######################################################
        self.combo = self.findChild((QComboBox), 'lookInCombo', Qt.FindDirectChildrenOnly)
        self.combo.setEditable(True)
        self.cb_line_edit = self.combo.lineEdit()
        self.cb_line_edit.editingFinished.connect(self.set_dir)
        for view in self.findChildren((QListView, QTreeView)):
            if isinstance(view.model(), QFileSystemModel):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.btn = None
        self.btns = [c for c in self.findChildren(QPushButton) if c.text() == '&Choose']
        if self.btns:
            self.btn = self.btns[0]
            self.btn.installEventFilter(self)
                
    def select_directories(self):
        self.directories_selected.emit(self.selectedFiles())
        self.close()
    
    def accept(self):
        pass

    def set_dir(self):
        self.setDirectory(self.cb_line_edit.text())
        
    def eventFilter(self, obj, event):
        if self.btn:
            if obj == self.btn and event.type() == QEvent.MouseButtonRelease:
                self.select_directories()
                return True
        return False

#################################################################################################
