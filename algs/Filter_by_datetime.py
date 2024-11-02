from processing.gui.wrappers import WidgetWrapper

from qgis.PyQt.QtCore import QCoreApplication, QVariant, QDateTime, Qt

from qgis.PyQt.QtWidgets import (QWidget, QLabel, QDateTimeEdit,
                                    QVBoxLayout, QHBoxLayout,
                                    QDialog, QTabWidget)
                                    
from qgis.PyQt.QtGui import QIcon

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsMapLayerProxyModel, QgsFieldProxyModel)
                        
from qgis.gui import (QgsMapLayerComboBox, QgsFieldComboBox)

from qgis.utils import iface

import os

                       
class FilterByDateTime(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "filterbydatetime"
         
    def displayName(self):
        return "Filter by datetime"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/collar_icon.png"))
 
    def shortHelpString(self):
        return "Filter a GPS collar point layer by a datetime range.\
        The start and end dates of the date range can be selected\
        using the provided date selection widgets."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading
        
    def checkParameterValues(self, parameters, context):
        # TODO: Add a check for a valid datetime field
        custom_params_list = self.parameterAsMatrix(parameters, self.INPUT_PARAMS, context)
        start_datetime = custom_params_list[2]
        end_datetime = custom_params_list[3]
        if end_datetime < start_datetime:
            return False, 'Invalid datetime range. End datetime is earlier than start datetime.'
        return super().checkParameterValues(parameters, context)
   
    def initAlgorithm(self, config=None):
        custom_input_params = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input parameters')
        custom_input_params.setMetadata({'widget_wrapper': {'class': CustomInputParameterWidgetWrapper}})
        self.addParameter(custom_input_params)

 
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        custom_params_list = self.parameterAsMatrix(parameters, self.INPUT_PARAMS, context)
        
        gps_collar_lyr = custom_params_list[0]
        datetime_fld = custom_params_list[1]
        start_datetime = custom_params_list[2]
        end_datetime = custom_params_list[3]
        
        start_date_string = start_datetime.toString('yyyy-MM-ddThh:mm:ss')
        end_date_string = end_datetime.toString('yyyy-MM-ddThh:mm:ss')
        
        filter_string = f""""{datetime_fld}" >= '{start_date_string}' and "{datetime_fld}" <= '{end_date_string}'"""
        
        gps_collar_lyr.setSubsetString(filter_string)

        return results
        '''
        return {'Layer': gps_collar_lyr,
                'DateTime Field': datetime_fld,
                'Start DateTime': start_datetime,
                'End DateTime': end_datetime}
        '''

    def postProcessAlgorithm(self, context, feedback):
        # hack to work around ?bug where, if algorithm returns the NoThreading flag,
        # the dialog reverts to the Parameters tab instead of showing the Log tab with results
        alg_dlg = [d for d in iface.mainWindow().findChildren(QDialog)if d.objectName() == 'QgsProcessingDialogBase' and d.isVisible()]
        tab_widg = alg_dlg[0].findChildren(QTabWidget)
        current_tab = tab_widg[0].currentIndex()
        if current_tab == 0:
            tab_widg[0].setCurrentIndex(1)
        return {}
        
#####################CUSTOM WIDGET WRAPPER####################
class CustomInputParameterWidgetWrapper(WidgetWrapper):
    def createWidget(self):
        self.cpw = CustomInputWidget()
        return self.cpw
        
    def value(self):
        input_params = [self.cpw.get_layer(),
                        self.cpw.get_datetime_field(),
                        self.cpw.get_start_datetime(),
                        self.cpw.get_end_datetime()]
        return input_params
        
#####################CUSTOM WIDGET CLASS####################
class CustomInputWidget(QWidget):
    def __init__(self):
        super(CustomInputWidget, self).__init__()
        
        self.lyr_lbl = QLabel('Input GPS point layer', self)
        self.lyr_cb = QgsMapLayerComboBox(self)
        self.lyr_cb.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.lyr_cb.layerChanged.connect(self.layer_changed)
        
        self.gps_lyr = self.lyr_cb.currentLayer()
        
        self.dt_fld_lbl = QLabel('Field containing datetime attribute', self)
        self.dt_fld_cb = QgsFieldComboBox(self)
        self.dt_fld_cb.setFilters(QgsFieldProxyModel.DateTime)
        self.dt_fld_cb.setLayer(self.lyr_cb.currentLayer())
        self.dt_fld_cb.fieldChanged.connect(self.set_widget_date_ranges)
        
        self.dtr_lbl = QLabel('Date/Time range for filter', self)
        
        self.start_dt_lbl = QLabel('Start Date-Time:', self)
        self.start_dt_edit = QDateTimeEdit(self)
        self.start_dt_edit.setMinimumWidth(140)
        self.start_dt_edit.setCalendarPopup(True)
                
        self.end_dt_lbl = QLabel('End Date-Time:', self)
        self.end_dt_edit = QDateTimeEdit(self)
        self.end_dt_edit.setMinimumWidth(140)
        self.end_dt_edit.setCalendarPopup(True)

        if self.gps_lyr:
            self.set_widget_date_ranges()
        
        self.main_layout = QVBoxLayout(self)
        self.date_layout = QHBoxLayout(self)
        self.date_layout.addWidget(self.start_dt_lbl, False, Qt.AlignLeft)
        self.date_layout.addWidget(self.start_dt_edit, False, Qt.AlignLeft)
        self.date_layout.addStretch()
        self.date_layout.addWidget(self.end_dt_lbl, False, Qt.AlignLeft)
        self.date_layout.addWidget(self.end_dt_edit, False, Qt.AlignLeft)
        self.date_layout.addStretch()
        self.main_layout.addWidget(self.lyr_lbl)
        self.main_layout.addWidget(self.lyr_cb)
        self.main_layout.addWidget(self.dt_fld_lbl)
        self.main_layout.addWidget(self.dt_fld_cb)
        self.main_layout.addWidget(self.dtr_lbl)
        self.main_layout.addLayout(self.date_layout)
                
    def layer_changed(self, lyr):
        if not lyr:
            return
        self.dt_fld_cb.setLayer(lyr)
        self.gps_lyr = lyr
        self.set_widget_date_ranges()
        
    def set_widget_date_ranges(self):
        gps_fts = [ft for ft in self.gps_lyr.getFeatures()]
        dt_fld = self.dt_fld_cb.currentField()
        dt_fld_idx = self.gps_lyr.fields().lookupField(dt_fld)
        dt_fld_obj = self.gps_lyr.fields()[dt_fld_idx]
        if not dt_fld or not gps_fts:
            self.start_dt_edit.setMinimumDateTime(QDateTime.currentDateTime())
            self.start_dt_edit.setMaximumDateTime(QDateTime.currentDateTime())
            self.start_dt_edit.setStyleSheet('color: red')
            self.end_dt_edit.setMinimumDateTime(QDateTime.currentDateTime())
            self.end_dt_edit.setMaximumDateTime(QDateTime.currentDateTime())
            self.end_dt_edit.setStyleSheet('color: red')
            return
        self.start_dt_edit.setStyleSheet('color: black')
        self.end_dt_edit.setStyleSheet('color: black')
        first_feat = gps_fts[0]
        last_feat = gps_fts[-1]
        first_dt = first_feat[dt_fld]
        last_dt = last_feat[dt_fld]

        start_y = first_dt.date().year()
        start_m = first_dt.date().month()
        start_d = first_dt.date().day()
        
        end_y = last_dt.date().year()
        end_m = last_dt.date().month()
        end_d = last_dt.date().day()
        
        min_start_dt = QDateTime(start_y, start_m, start_d, 0, 0, 0)
        self.start_dt_edit.setMinimumDateTime(min_start_dt)
        max_start_dt = QDateTime(end_y, end_m, end_d, 0, 0, 0)
        self.start_dt_edit.setMaximumDateTime(max_start_dt)
        self.start_dt_edit.setDateTime(min_start_dt)
        
        min_end_dt = QDateTime(start_y, start_m, start_d, 23, 59, 0)
        self.end_dt_edit.setMinimumDateTime(min_end_dt)
        max_end_dt = QDateTime(end_y, end_m, end_d, 23, 59, 0)
        self.end_dt_edit.setMaximumDateTime(max_end_dt)
        self.end_dt_edit.setDateTime(max_end_dt)
    
    def get_layer(self):
        return self.gps_lyr # QgsVectorLayer object
        
    def get_datetime_field(self):
        return self.dt_fld_cb.currentField()# Field name string
        
    def get_start_datetime(self):
        return self.start_dt_edit.dateTime()
        
    def get_end_datetime(self):
        return self.end_dt_edit.dateTime()
