from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtWidgets import QDialog, QTabWidget
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterVectorLayer,
                        QgsProcessingParameterFileDestination,
                        QgsCategorizedSymbolRenderer)

from qgis.utils import iface

import csv

import os


class ExportColorMapToCsv(QgsProcessingAlgorithm):
    LAYER = 'LAYER'
    OUTPUT_CSV_PATH = 'OUTPUT_CSV_PATH'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "exportcolormaptocsv"
         
    def displayName(self):
        return "Export color map to CSV"
 
    def group(self):
        return "General"
 
    def groupId(self):
        return "general"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/col_map_icon.png"))
 
    def shortHelpString(self):
        return "Export a color map from a categorised vector layer to a CSV file\
                The CSV will contain the renderer class values, hex codes and\
                RGB values of the associated category colors."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.LAYER,
            "Input layer",
            [QgsProcessing.TypeVectorAnyGeometry]))
            
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_CSV_PATH,
            "Output CSV file",
            "*.csv"))

    def checkParameterValues(self, parameters, context):
        layer = self.parameterAsVectorLayer(parameters, self.LAYER, context)
        result_csv = self.parameterAsFileOutput(parameters, self.OUTPUT_CSV_PATH, context)
        r = layer.renderer()
        if not isinstance(r, QgsCategorizedSymbolRenderer):
            return False, 'Input layer is not using a categorized symbol render.'
        if parameters[self.OUTPUT_CSV_PATH] == 'TEMPORARY_OUTPUT':
            return False, 'Please select an output file location (not a temporary output).'
        return super().checkParameterValues(parameters, context)
 
    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.LAYER, context)
        result_csv = self.parameterAsFileOutput(parameters, self.OUTPUT_CSV_PATH, context)
        ################################

        csv_tbl = open(result_csv, mode='w', newline='')
        writer = csv.writer(csv_tbl)
        r = layer.renderer()
        if not isinstance(r, QgsCategorizedSymbolRenderer):
            return {}
        class_attribute = r.classAttribute()
        writer.writerow([class_attribute, 'Hex Code', 'RGB(A) Values'])
        for cat in r.categories():
            ls = cat.value()
            col = cat.symbol().color()
            hex_code = col.name()
            r_val = col.rgba64().red8()
            g_val = col.rgba64().green8()
            b_val = col.rgba64().blue8()
            a_val = col.rgba64().alpha8()
            if a_val != 255:
                rgba_string = f'{r_val}, {g_val}, {b_val}, {a_val}'
            else:
                rgba_string = f'{r_val}, {g_val}, {b_val}'
            writer.writerow([ls, hex_code, rgba_string])
        csv_tbl.close()
        ################################

        return {'Color map CSV': result_csv}
        
    def postProcessAlgorithm(self, context, feedback):
        # hack to work around ?bug where, if algorithm returns the NoThreading flag,
        # the dialog reverts to the Parameters tab instead of showing the Log tab with results
        alg_dlg = [d for d in iface.mainWindow().findChildren(QDialog)if d.objectName() == 'QgsProcessingDialogBase' and d.isVisible()]
        tab_widg = alg_dlg[0].findChildren(QTabWidget)
        current_tab = tab_widg[0].currentIndex()
        if current_tab == 0:
            tab_widg[0].setCurrentIndex(1)
        return {}
        