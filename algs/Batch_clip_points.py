from qgis.PyQt.QtCore import (QCoreApplication, QVariant)
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFile,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterFolderDestination,
                        QgsFeatureRequest,
                        QgsProcessingMultiStepFeedback)
import os
import processing
                       
class BatchClipPoints(QgsProcessingAlgorithm):
    INPUT_DIR = 'INPUT_DIR'
    PADDOCKS = 'PADDOCKS'
    OUTPUT_DIR = 'OUTPUT_DIR'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "batchclippoints"
         
    def displayName(self):
        return "Batch clip points"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Clip all raw GPS collar point GeoPackages in an input\
        folder to a paddock or buffered paddock polygon and save to an output folder"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT_DIR,
            'Source Folder',
            behavior=QgsProcessingParameterFile.Folder))
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.PADDOCKS,
            "Clip Layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_DIR,
            "Output Folder"))
 
    def processAlgorithm(self, parameters, context, model_feedback):        
        results = {}
        
        source_folder = self.parameterAsFile(parameters, self.INPUT_DIR, context)
        
        clip_src = self.parameterAsSource(parameters, self.PADDOCKS, context)
        clip_lyr = clip_src.materialize(QgsFeatureRequest())
        
        output_folder = parameters[self.OUTPUT_DIR]
 
        if not os.path.exists(output_folder):
            os.mkdir(output_folder)
    
        steps = len([f for f in os.scandir(source_folder) if f.name.split('.')[-1] == 'gpkg'])
        
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        
        step = 0
        
        for f in os.scandir(source_folder):
            if not f.name.split('.')[-1] == 'gpkg':
                continue
            in_path = os.path.join(source_folder, f.name)
            out_path = os.path.join(output_folder, f.name)
            
            clip_params = {'INPUT': in_path,
                            'OVERLAY': clip_lyr,
                            'OUTPUT': out_path}
            
            feedback.setCurrentStep(step)
            result = processing.run('native:clip', clip_params, is_child_algorithm=True, feedback=feedback, context=context)
            results[f.name.split('.')[0]] = result['OUTPUT']
            step+=1
            
        return results