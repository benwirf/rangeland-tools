from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (QgsProcessing,
                        QgsProcessingUtils,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterRasterLayer,
                        QgsProcessingParameterBoolean,
                        QgsProcessingParameterRasterDestination,
                        QgsProcessingMultiStepFeedback)

import processing
                       
class InvertRaster(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    OUTPUT_RASTER = 'OUTPUT_RASTER'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "invertraster"
         
    def displayName(self):
        return "Invert raster"
 
    def group(self):
        return "Raster General"
 
    def groupId(self):
        return "raster_general"
 
    def shortHelpString(self):
        return "Invert positive/negative cell values in a raster layer (multiply by -1)."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_RASTER, 'Input raster'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_RASTER, 'Inverted raster'))
 
    def processAlgorithm(self, parameters, context, model_feedback):
        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        feedback.setCurrentStep(1)
        #######################################################################

        #######################################################################
        calc_params = {'EXPRESSION':f'"{input_raster.name()}@1"*-1',
                        'LAYERS':[input_raster],
                        'CELLSIZE':0,
                        'EXTENT':None,
                        'CRS':None,
                        'OUTPUT':output_raster}
        processing.run("qgis:rastercalculator", calc_params)
        #######################################################################
 
        return {self.OUTPUT_RASTER: output_raster}