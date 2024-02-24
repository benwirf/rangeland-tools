from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtWidgets import (QWidget, QComboBox, QLabel, QPushButton,
                                QTableWidget, QHBoxLayout, QTableWidgetItem,
                                QVBoxLayout, QDialog)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import (QCoreApplication, Qt, QVariant, QDate, QDateTime)
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink, QgsFeatureRequest,
                        QgsFields, QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField, QgsProject,
                        QgsProcessingParameterString,
                        QgsProcessingParameterFeatureSink)
from qgis.utils import iface
from datetime import datetime
                       
class AddDateTimeField(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    DATE_FIELD = 'DATE_FIELD'
    DATE_STRING_FORMAT = 'DATE_STRING_FORMAT'
    TIME_FIELD = 'TIME_FIELD'
    TIME_STRING_FORMAT = 'TIME_STRING_FORMAT'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "adddatetimefield"
         
    def displayName(self):
        return "Add date time field"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Add a QDateTime field from a string field containing date/time information"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            "Input layer",
            [QgsProcessing.TypeVectorAnyGeometry]))
        
        ########DATE FIELD##############################################
        self.addParameter(QgsProcessingParameterField(
            self.DATE_FIELD,
            "Field containing date string",
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.String))
        
        format_param = QgsProcessingParameterString(self.DATE_STRING_FORMAT, 'Date String Format')
        format_param.setMetadata({'widget_wrapper': {'class': CustomDateFormatParameterWidgetWrapper}})
        self.addParameter(format_param)
        #################################################################
        
        ########TIME FIELD##############################################
        self.addParameter(QgsProcessingParameterField(
            self.TIME_FIELD,
            "Field containing time string",
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.String))
        
        format_param = QgsProcessingParameterString(self.TIME_STRING_FORMAT, 'Time String Format')
        format_param.setMetadata({'widget_wrapper': {'class': CustomTimeFormatParameterWidgetWrapper}})
        self.addParameter(format_param)
        #################################################################
            
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Output layer",
            QgsProcessing.TypeVectorAnyGeometry))
 
    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        date_fields = self.parameterAsFields(parameters, self.DATE_FIELD, context)
        date_string_field = date_fields[0]# This is a string literal, not a QgsField object
        date_format = self.parameterAsString(parameters, self.DATE_STRING_FORMAT, context)
        ###
        time_fields = self.parameterAsFields(parameters, self.TIME_FIELD, context)
        time_string_field = time_fields[0]# This is a string literal, not a QgsField object
        time_format = self.parameterAsString(parameters, self.TIME_STRING_FORMAT, context)
        ###
        flds = [fld for fld in source.fields()]
        new_fld_idx = source.fields().lookupField(date_string_field)+1
        datetime_field = QgsField('q_datetime', QVariant.DateTime)
        flds.insert(new_fld_idx, datetime_field)
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
            #Parse DateTime###########################################
            if date_string_field == time_string_field:
                # Date and Time are both in a single field e.g. '2023-05-10 05:57:34Z'
                # So we can parse a datetime object from either input
                dt = datetime.strptime(ft[date_string_field], date_format)
            elif date_string_field != time_string_field:
                # Date and time info is in separate fields
                # So we need to parse separately then combine
                dd = datetime.strptime(ft[date_string_field], date_format)
                tt = datetime.strptime(ft[time_string_field], time_format)
                dt = datetime.combine(dd.date(), tt.time())
            qdtd = QDateTime(dt)
            #########################################################
            atts.insert(new_fld_idx, qdtd)
            feat.setAttributes(atts)
            all_feats.append(feat)
        
        sink.addFeatures(all_feats)
        
        return {self.OUTPUT: dest_id}

########## Custom Date Parameter Widget Wrapper########################
class CustomDateFormatParameterWidgetWrapper(WidgetWrapper):
    def createWidget(self):
        self.cdfw = CustomDateFormatWidget()
        return self.cdfw
        
    def value(self):
        return self.cdfw.getDateFormat()
        
########## Custom Time Parameter Widget Wrapper########################
class CustomTimeFormatParameterWidgetWrapper(WidgetWrapper):
    def createWidget(self):
        self.ctfw = CustomTimeFormatWidget()
        return self.ctfw
        
    def value(self):
        return self.ctfw.getTimeFormat()

########## Custom Date Parameter Widget ################################
class CustomDateFormatWidget(QWidget):
    def __init__(self):
        super(CustomDateFormatWidget, self).__init__()
        self.format_cb = QComboBox(self)
        self.format_cb.addItems(self.common_formats())
        self.format_cb.setEditable(True)
        self.help_btn = QPushButton(QIcon(":images/themes/default/propertyicons/metadata.svg"), '', self)
        self.help_btn.setToolTip('Get Help')
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.format_cb, 1)
        self.layout.addWidget(self.help_btn)
        
        self.date_help_widget = DateHelpWidget(self)
        self.help_btn.clicked.connect(self.show_date_help)

    def show_date_help(self):
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
            self.date_help_widget.sample_label.setText(f'Sample value from current layer/field: {sample_val}')
        else:
            self.date_help_widget.sample_label.setText('Sample value not available')
        alg_dlg_geom = alg_dlg.geometry()
        cntr = alg_dlg_geom.center()# QPoint
        #self.date_help_widget.geometry().moveCenter(cntr)
        self.date_help_widget.show()
        self.date_help_widget.geometry().moveCenter(cntr)
    
    def common_formats(self):
        return ['%Y-%m-%d %H:%M:%SZ',
                '%d/%m/%Y %H:%M:%S',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%Y-%m-%d',
                '%Y/%m/%d']
                
    def getDateFormat(self):
        return self.format_cb.currentText()
        
        
class DateHelpWidget(QWidget):
    def __init__(self, parent=None):
        super(DateHelpWidget, self).__init__()
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
        self.setMinimumWidth(self.tbl.columnWidth(0)+self.tbl.columnWidth(1)+50)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.sample_label)
        self.layout.addWidget(self.help_label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.tbl)

        
########## Custom Time Parameter Widget ################################
class CustomTimeFormatWidget(QWidget):
    def __init__(self):
        super(CustomTimeFormatWidget, self).__init__()
        self.format_cb = QComboBox(self)
        self.format_cb.addItems(self.common_formats())
        self.format_cb.setEditable(True)
        self.help_btn = QPushButton(QIcon(":images/themes/default/propertyicons/metadata.svg"), '', self)
        self.help_btn.setToolTip('Get Help')
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.format_cb, 1)
        self.layout.addWidget(self.help_btn)
        
        self.time_help_widget = TimeHelpWidget(self)
        self.help_btn.clicked.connect(self.show_time_help)

    def show_time_help(self):
        # So hacky and ugly :-( ... but does the job :-)
        # We just want to show a sample of the format in the selected field
        # of the selected layer...
        alg_dlg = [d for d in iface.mainWindow().findChildren(QDialog)if d.objectName() == 'QgsProcessingDialogBase' and d.isVisible()][0]
        combo_boxes = alg_dlg.findChildren(QComboBox)
        lyr_name = combo_boxes[0].currentText()
        fld_name = combo_boxes[3].currentText()
        lyrs = QgsProject.instance().mapLayersByName(lyr_name.split('[')[0].rstrip())
        if lyrs:
            lyr = lyrs[0]
            sample_val = next(lyr.getFeatures())[fld_name]
            self.time_help_widget.sample_label.setText(f'Sample value from current layer/field: {sample_val}')
        else:
            self.time_help_widget.sample_label.setText('Sample value not available')
        alg_dlg_geom = alg_dlg.geometry()
        cntr = alg_dlg_geom.center()# QPoint
        self.time_help_widget.geometry().moveCenter(cntr)
        self.time_help_widget.show()
    
    def common_formats(self):
        return ['%Y-%m-%d %H:%M:%SZ',
                '%d/%m/%Y %H:%M:%S',
                '%H:%M:%S']
                
    def getTimeFormat(self):
        return self.format_cb.currentText()
        
        
class TimeHelpWidget(QWidget):
    def __init__(self, parent=None):
        super(TimeHelpWidget, self).__init__()
        self.sample_label = QLabel('')
        self.help_label = QLabel('See table below for common date/time strings \n\
        and corresponding datetime formats', self)
        self.rows = [['2022-05-18 20:35:20Z', '%Y-%m-%d %H:%M:%SZ'],
                    ['18/05/2022 00:06:02', '%d/%m/%Y %H:%M:%S'],
                    ['08:10:24', '%H:%M:%S']]
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(2)
        self.tbl.setRowCount(3)
        self.tbl.setHorizontalHeaderLabels(['String Format', 'DateTime Format'])
        for row in range(self.tbl.rowCount()):
            for col in range(self.tbl.columnCount()):
                item = QTableWidgetItem(self.rows[row][col])
                self.tbl.setItem(row, col, item)
        self.tbl.resizeColumnsToContents()
        self.tbl.setStyleSheet('color: blue')
        self.setMinimumWidth(self.tbl.columnWidth(0)+self.tbl.columnWidth(1)+50)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.sample_label)
        self.layout.addWidget(self.help_label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.tbl)
        