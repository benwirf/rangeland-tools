from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (QgsProcessing,
                        QgsProcessingUtils,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterRasterLayer,
                        QgsProcessingParameterBoolean,
                        QgsProcessingParameterRasterDestination,
                        QgsProcessingMultiStepFeedback)
                        
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry

import processing
                       
class DeltaNBR(QgsProcessingAlgorithm):
    PRE_FIRE_NBR_RASTER = 'PRE_FIRE_NBR_RASTER'
    POST_FIRE_NBR_RASTER = 'POST_FIRE_NBR_RASTER'
    OUTPUT_RASTER = 'OUTPUT_RASTER'
    INVERT_OUTPUT = 'INVERT_OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "deltanbr"
         
    def displayName(self):
        return "Calculate dNBR"
 
    def group(self):
        return "Fire Mapping"
 
    def groupId(self):
        return "fire_mapping"
 
    def shortHelpString(self):
        return "Subtract a post-fire NBR raster from a pre-fire NBR raster\
                to calculate a difference (delta) NBR raster enabling extraction\
                of burnt area and estimation of fire intensity."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRE_FIRE_NBR_RASTER, 'Pre-Fire NBR raster'))
        self.addParameter(QgsProcessingParameterRasterLayer(self.POST_FIRE_NBR_RASTER, 'Post-Fire NBR raster'))
        self.addParameter(QgsProcessingParameterBoolean(self.INVERT_OUTPUT, 'Invert output raster (multiply by -1)'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_RASTER, 'Delta NBR'))
 
    def processAlgorithm(self, parameters, context, model_feedback):
        pre_fire_nbr_raster = self.parameterAsRasterLayer(parameters, self.PRE_FIRE_NBR_RASTER, context)
        post_fire_nbr_raster = self.parameterAsRasterLayer(parameters, self.POST_FIRE_NBR_RASTER, context)
        output_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        invert_output = self.parameterAsBool(parameters, self.INVERT_OUTPUT, context)
        
        steps = 1
        if invert_output:
            steps = 2
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        feedback.setCurrentStep(1)
        #######################################################################
        results = ['Calculation successful',
                    'Error creating output data file',
                    'Error reading input layer',
                    'User canceled calculation',
                    'Error parsing formula',
                    'Error allocating memory for result',
                    'Invalid band number for input',
                    'Error occurred while performing calculation']
        #######################################################################
        rc_entries = []
        ###
        pre_burn_entry = QgsRasterCalculatorEntry()
        pre_burn_entry.ref = 'pre_fire_nbr'
        pre_burn_entry.raster = pre_fire_nbr_raster
        pre_burn_entry.bandNumber = 1
        rc_entries.append(pre_burn_entry)

        post_burn_entry = QgsRasterCalculatorEntry()
        post_burn_entry.ref = 'post_fire_nbr'
        post_burn_entry.raster = post_fire_nbr_raster
        post_burn_entry.bandNumber = 1
        rc_entries.append(post_burn_entry)
        
        rc_expression = '"pre_fire_nbr"-"post_fire_nbr"'
        bbox = pre_fire_nbr_raster.extent()
        crs = pre_fire_nbr_raster.crs()
        width = pre_fire_nbr_raster.width()
        height = pre_fire_nbr_raster.height()
        ###
        temp_dest = QgsProcessingParameterRasterDestination(name="dnbr").generateTemporaryDestination()
        ###
        calc = QgsRasterCalculator(rc_expression,
                                   temp_dest if invert_output else output_raster,
                                   'GTiff',
                                   bbox,
                                   crs,
                                   width,
                                   height,
                                   rc_entries)
                                   
        res = calc.processCalculation(feedback)
        feedback.pushInfo(results[res])
        calc = None
        del calc
        rc_entries.clear()
        #######################################################################
        if invert_output:
            feedback.setCurrentStep(2)
            temp_lyr = QgsProcessingUtils.mapLayerFromString(temp_dest, context)
            calc_params = {'EXPRESSION':f'"{temp_lyr.name()}@1"*-1',
                            'LAYERS':[temp_dest],
                            'CELLSIZE':0,
                            'EXTENT':None,
                            'CRS':None,
                            'OUTPUT':output_raster}
            processing.run("qgis:rastercalculator", calc_params)
        #######################################################################
 
        return {self.OUTPUT_RASTER: output_raster}