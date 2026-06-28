from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterRasterLayer,
                        QgsProcessingParameterNumber,
                        QgsProcessingParameterEnum,
                        QgsProcessingParameterRasterDestination,
                        QgsProcessingMultiStepFeedback,
                        QgsProcessingUtils)

import processing
                       
class ExtractRasterWithThreshold(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    THRESHOLD_VALUE = 'THRESHOLD_VALUE'
    THRESHOLD_DIRECTION = 'THRESHOLD_DIRECTION'
    OUTPUT_RASTER = 'OUTPUT_RASTER'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "extractwiththreshold"
         
    def displayName(self):
        return "Extract raster with threshold"
 
    def group(self):
        return "Raster General"
 
    def groupId(self):
        return "raster_general"
 
    def shortHelpString(self):
        return "Extract raster cells above or below a given threshold entered by the user.\
                Output is a binary raster where cells meeting the threshold are 1."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_RASTER, 'Input raster'))
        self.addParameter(QgsProcessingParameterEnum(self.THRESHOLD_DIRECTION, 'Threshold direction', ['Above', 'Below'], defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.THRESHOLD_VALUE, 'Threshold value', QgsProcessingParameterNumber.Double))
        self.parameterDefinition(self.THRESHOLD_DIRECTION).setMetadata({'widget_wrapper': {'useCheckBoxes': True, 'columns': 2}})
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_RASTER, 'Output raster'))
        
    def checkParameterValues(self, parameters, context):
        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        threshold_value = self.parameterAsDouble(parameters, self.THRESHOLD_VALUE, context)
        threshold_direction = self.parameterAsEnum(parameters, self.THRESHOLD_DIRECTION, context)
        comparison_operators = {'Above': '>', 'Below': '<'}
        comparison_operator = comparison_operators[list(comparison_operators.keys())[threshold_direction]]
        band_stats = input_raster.dataProvider().bandStatistics(1)
        min = band_stats.minimumValue
        max = band_stats.maximumValue
        if comparison_operator == '>' and threshold_value > max:
            return False, 'Threshold value is higher than maximum value in input raster.\
                    please enter a lower threshold value.'
        elif comparison_operator == '<' and threshold_value < min:
            return False, 'Threshold value is lower than minimum value in input raster.\
                    please enter a higher threshold value.'
        return super().checkParameterValues(parameters, context)
 
    def processAlgorithm(self, parameters, context, model_feedback):
        input_raster = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        
        threshold_value = self.parameterAsDouble(parameters, self.THRESHOLD_VALUE, context)
        threshold_direction = self.parameterAsEnum(parameters, self.THRESHOLD_DIRECTION, context)
        comparison_operators = {'Above': '>', 'Below': '<'}
        comparison_operator = comparison_operators[list(comparison_operators.keys())[threshold_direction]]

        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        feedback.setCurrentStep(1)
        #######################################################################
        #'"Output@1">0.05'
        #######################################################################
        
        calc_params = {'EXPRESSION':f'"{input_raster.name()}@1"{comparison_operator}{threshold_value}',
                        'LAYERS':[input_raster],
                        'CELLSIZE':0,
                        'EXTENT':None,
                        'CRS':None,
                        'OUTPUT':output_raster}
        processing.run("qgis:rastercalculator", calc_params)
        #######################################################################
        ###Rename output layer###
        if context.willLoadLayerOnCompletion(output_raster):
            details = context.layerToLoadOnCompletionDetails(output_raster)
            l = QgsProcessingUtils.mapLayerFromString(output_raster, context, typeHint=details.layerTypeHint)
            #feedback.pushInfo(l.name())
            if l.name() == 'OUTPUT_RASTER':
                new_name = f'{["above", "below"][threshold_direction]}_{threshold_value}'
                details.name = new_name
                details.forceName = True

        return {self.OUTPUT_RASTER: output_raster}