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
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField,
                        QgsProcessingParameterFolderDestination,
                        QgsWkbTypes)

import os
import shutil
                       
class CopyMSImages(QgsProcessingAlgorithm):
    INPUT_DIRS = 'INPUT_DIRS'
    POINT_LAYER = 'POINT_LAYER'
    NAME_FIELD = 'NAME_FIELD'
    DEST_FOLDER = 'DEST_FOLDER'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "copymsimages"
         
    def displayName(self):
        return "Copy MS Images"
 
    def group(self):
        return "Drone Mapping"
 
    def groupId(self):
        return "dronemapping"
 
    def shortHelpString(self):
        return "Copy raw multispectral TIF images from multiple DJI folders to a \
        separate folder ready for importing to photogrammetry software\
        such as Agisoft or WebODM.\
        \nNote: Input directories are not searched recursively. If no\
        TIF images are found in the first level of source directories,\
        no files will be copied."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        input_dirs = QgsProcessingParameterMatrix(self.INPUT_DIRS, 'Source directories')
        input_dirs.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(input_dirs)
        
        self.addParameter(QgsProcessingParameterFeatureSource(self.POINT_LAYER,
                                                                'Point layer containing image locations/names',
                                                                types=[QgsProcessing.TypeVectorPoint]))
                                                                
        self.addParameter(QgsProcessingParameterField(self.NAME_FIELD,
                                                        'Field containing image name',
                                                        parentLayerParameterName=self.POINT_LAYER,
                                                        type=QgsProcessingParameterField.String))
                                                        
        self.addParameter(QgsProcessingParameterFolderDestination(self.DEST_FOLDER,
                                                                    'Destination folder'))
        

    def processAlgorithm(self, parameters, context, feedback):
        # Retrieve the list of parameters returned by the custom widget wrapper
        input_dirs_list = self.parameterAsMatrix(parameters, self.INPUT_DIRS, context)
        
        point_layer = self.parameterAsSource(parameters, self.POINT_LAYER, context)
        
        name_fields = self.parameterAsFields(parameters, self.NAME_FIELD, context)#String list
        fld_name = name_fields[0]
        
        dest_folder_path = self.parameterAsString(parameters, self.DEST_FOLDER, context)

        subset_names = [ft[fld_name] for ft in point_layer.getFeatures()]
        
        cnt = 0
        total_count = len(subset_names)
        
        for folder_path in input_dirs_list:
            if feedback.isCanceled():
                break
            for f in os.scandir(folder_path):
                if feedback.isCanceled():
                    break
                if not 'TIF' in f.name:
                    continue
                if len(f.name.split('.')) == 2 and f.name.split('.')[1] == 'TIF':
                    if f.name.split('.')[0] in subset_names:
                        cnt+=1
                        src = f.path
                        shutil.copy2(src, dest_folder_path)
                        pcnt = (cnt/total_count)*100
                        feedback.setProgress(round(pcnt, 5))
                                
        if cnt == 0:
            feedback.pushWarning('No multispectral TIF images found')
        else:
            feedback.pushInfo(f'Copied {cnt} multispectral TIF images')

        return {'INPUT_DIRS': input_dirs_list,
                'POINT_LAYER': point_layer,
                'NAME_FIELD': fld_name,
                'DEST_FOLDER': dest_folder_path}
        

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