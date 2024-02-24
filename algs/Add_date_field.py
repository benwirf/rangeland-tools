from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtWidgets import (QWidget, QComboBox, QLabel, QPushButton,
                                QTableWidget, QHBoxLayout, QTableWidgetItem,
                                QVBoxLayout, QDialog)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import (QCoreApplication, Qt, QVariant, QDate, QRect)
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink, QgsFeatureRequest,
                        QgsFields, QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField, QgsProject,
                        QgsProcessingParameterString,
                        QgsProcessingParameterFeatureSink)
from qgis.utils import iface
from datetime import datetime
                       
class AddDateField(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    DATE_FIELD = 'DATE_FIELD'
    STRING_FORMAT = 'STRING_FORMAT'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "adddatefield"
         
    def displayName(self):
        return "Add date field"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Add a QDate field from a string field containing date/time information"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            "Input layer",
            [QgsProcessing.TypeVectorAnyGeometry]))
            
        self.addParameter(QgsProcessingParameterField(
            self.DATE_FIELD,
            "Field containing date string",
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.String))
        
        format_param = QgsProcessingParameterString(self.STRING_FORMAT, 'DateTime Format')
        format_param.setMetadata({'widget_wrapper': {'class': CustomParametersWidgetWrapper}})
        self.addParameter(format_param)
            
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Output layer",
            QgsProcessing.TypeVectorAnyGeometry))
 
    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        date_fields = self.parameterAsFields(parameters, self.DATE_FIELD, context)
        date_string_field = date_fields[0]
        datetime_format = self.parameterAsString(parameters, self.STRING_FORMAT, context)
        flds = [fld for fld in source.fields()]
        new_fld_idx = source.fields().lookupField(date_string_field)+1
        date_field = QgsField('q_date', QVariant.Date)
        flds.insert(new_fld_idx, date_field)
        output_flds = QgsFields()
        for fld in flds:
            output_flds.append(fld)
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_flds, source.wkbType(), source.sourceCrs())
        
        all_feats = []
        
        src_feat_count = source.featureCount()
        for i, ft in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            pcnt = ((i+1)/src_feat_count)*100
            feedback.setProgress(round(pcnt, 1))
            feat = QgsFeature(output_flds)
            feat.setGeometry(ft.geometry())
            atts = [att for att in ft.attributes()]
            dt = datetime.strptime(ft[date_string_field], datetime_format)
            qdtd = QDate(dt.date())
            atts.insert(new_fld_idx, qdtd)
            feat.setAttributes(atts)
            all_feats.append(feat)
        
        sink.addFeatures(all_feats)
        
        return {self.OUTPUT: dest_id}
                
class CustomParametersWidgetWrapper(WidgetWrapper):
    def createWidget(self):
        self.cfw = CustomFormatWidget()
        return self.cfw
        
    def value(self):
        return self.cfw.getFormat()

class CustomFormatWidget(QWidget):
    def __init__(self):
        super(CustomFormatWidget, self).__init__()
        #self.setGeometry(500, 300, 500, 200)
        self.format_cb = QComboBox(self)
        self.format_cb.addItems(self.common_formats())
        self.format_cb.setEditable(True)
        self.help_btn = QPushButton(QIcon(":images/themes/default/propertyicons/metadata.svg"), '', self)
        self.help_btn.setToolTip('Get Help')
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.format_cb, 1)
        self.layout.addWidget(self.help_btn)
        
        self.help_widget = HelpWidget(self)
        self.help_btn.clicked.connect(self.show_help)
        
    def show_help(self):
        # So hacky and ugly :-( ... but does the job :-)
        # We just want to show a sample of the format in the selected field
        # of the selected layer...
        alg_dlg = [d for d in iface.mainWindow().findChildren(QDialog)if d.objectName() == 'QgsProcessingDialogBase' and d.isVisible()][0]
        combo_boxes = alg_dlg.findChildren(QComboBox)
        lyr_name = combo_boxes[0].currentText()
        fld_name = combo_boxes[1].currentText()
        lyrs = QgsProject.instance().mapLayersByName(lyr_name.split('[')[0].rstrip())
        if lyrs:
            lyr = lyrs[0]
            sample_val = next(lyr.getFeatures())[fld_name]
            self.help_widget.sample_label.setText(f'Sample value from current layer/field: {sample_val}')
        else:
            self.help_widget.sample_label.setText('Sample value not available')
        
        #Show help widget at center of open algorithm dialog (works... kind of)
        #Geometry: PyQt5.QtCore.QRect(223, 112, 1408, 862)
        #Center: PyQt5.QtCore.QPoint(940, 418)
        alg_dlg_geom = alg_dlg.geometry()
        cntr = alg_dlg_geom.center()# QPoint
        self.help_widget.geometry().moveCenter(cntr)
        self.help_widget.show()
    
    def common_formats(self):
        return ['%Y-%m-%d %H:%M:%SZ',
                '%d/%m/%Y %H:%M:%S',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%Y-%m-%d',
                '%Y/%m/%d']
                
    def getFormat(self):
        return self.format_cb.currentText()
        
        
class HelpWidget(QWidget):
    def __init__(self, parent=None):
        super(HelpWidget, self).__init__()
        self.sample_label = QLabel('')
        self.help_label = QLabel('See table below for common date/time strings \n\
        and corresponding datetime formats', self)
        self.rows = [['2022-05-18 20:35:20Z', '%Y-%m-%d %H:%M:%SZ'],
                    ['18/05/2022 00:06:02', '%d/%m/%Y %H:%M:%S'],
                    ['18-05-2022', '%d-%m-%Y'],
                    ['18/05/2022', '%d/%m/%Y'],
                    ['2022-05-18', '%Y-%m-%d'],
                    ['2022/05/18', '%Y/%m/%d']]
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(2)
        self.tbl.setRowCount(6)
        self.tbl.setHorizontalHeaderLabels(['String Format', 'DateTime Format'])
        for row in range(self.tbl.rowCount()):
            for col in range(self.tbl.columnCount()):
                item = QTableWidgetItem(self.rows[row][col])
                self.tbl.setItem(row, col, item)
        self.tbl.resizeColumnsToContents()
        self.tbl.setStyleSheet('color: blue')
        self.setMinimumWidth(self.tbl.columnWidth(0)+self.tbl.columnWidth(1)+75)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.sample_label)
        self.layout.addWidget(self.help_label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.tbl)
        