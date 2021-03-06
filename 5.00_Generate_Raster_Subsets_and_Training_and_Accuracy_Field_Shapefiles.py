
###############################################################################################
###############################################################################################

# Name:             5.00_Generate_Raster_Subsets_and _Training_and_Accuracy_Field_Shapefiles.py
# Author:           Kelly Meehan, USBR
# Created:          20190724
# Updated:          20200701 
# Version:          Created using Python 3.6.8 

# Requires:         ArcGIS Pro 

# Notes:            This script is intended to be used for a Script Tool within ArcGIS Pro; it is not intended as a stand-alone script.

# Description:      This tool generates shapefile and raster subsets of a field border shapefile and satellite image(s), respectively.  

#----------------------------------------------------------------------------------------------

# Tool setup:       The script tool's properties can be set as follows: 
#
#                      Parameters tab:    
#                           Edited Field Borders Shapefile  Feature Layer (Data Type) > Required (Type) > Input (Direction)                  
#                           Raw Image(s) (priority order)   Raster Dataset-Multivalue (Data Type) > Required (Type) > Input (Direction)                  
#                           Image Directory                 Workspace (Data Type) > Required (Type) > Input (Direction)                    
#                           Shapefile Directory             Workspace (Data Type) > Required (Type) > Input (Direction)                    
#
#                       Validation tab:
#
# import arcpy

# class ToolValidator(object):
#     """Class for validating a tool's parameter values and controlling
#     the behavior of the tool's dialog."""

#     def __init__(self):
#         """Setup arcpy and the list of tool parameters.""" 
#         self.params = arcpy.GetParameterInfo()

#     def initializeParameters(self):
#         """Refine the properties of a tool's parameters. This method is 
#         called when the tool is opened."""

#     def updateParameters(self):
#         """Modify the values and properties of parameters before internal
#         validation is performed. This method is called whenever a parameter
#         has been changed."""
        
#         # Set default directory for Shapefile Directory
#         if self.params[0].value:
#             if not self.params[3].altered:
#                 covs_directory = os.path.dirname(self.params[0].value.value) 
#                 self.params[3].value = covs_directory
#                 shapefile_name = os.path.basename(self.params[0].value.value)
#                 region_time_caps = shapefile_name.rsplit(sep = '_', maxsplit = 1)[0].upper()       
#             
#             # Set default directory for Image Directory        
#             if not self.params[2].altered:         
#                 img_directory = os.path.abspath(os.path.join(covs_directory, '..', 'img_' + region_time_caps))   
#                 self.params[2].value = img_directory
            
#     def updateMessages(self):
#         """Modify the messages created by internal validation for each tool
#         parameter. This method is called after internal validation."""

#     def isLicensed(self):
#         """Set whether tool is licensed to execute."""
#         return True

###############################################################################################
################################################################################################ 

# This script will:
# 0. Set up
# 1. Create Accuracy Fields Shapefile and Training Fields Shapefile, subset from Edited Fields Shapefile
# 2. Create Training Fields Mask Shapefile, 30 meter inner buffer mask of Training Fields Shapefile
# 3. Reproject rasters 
# 4. Mosaic rasters (if applicable)
# 5. Create three subsets from Mosaiced Raw Raster Image(s) or Raw Image 

#----------------------------------------------------------------------------------------------

# 0. Set up
 
# 0.0 Import necessary packages 
import arcpy, os, sys
from arcpy.sa import ExtractByMask

#--------------------------------------------

# 0.1 Read in tool parameters

# User selects Edited Field Borders Shapefile
edited_field_borders_shapefile = arcpy.GetParameterAsText(0) 

# User selects Raw Image(s) in order of priority (dominant raster first, etc.)
raw_raster_list = arcpy.GetParameterAsText(1).split(';')

# User selects Image Directory
img_path = arcpy.GetParameterAsText(2)

# User selects Coverage Directory
covs_path = arcpy.GetParameterAsText(3)

#--------------------------------------------

# 0.2 Set environment settings

# Overwrite output
arcpy.env.overwriteOutput = True

# Set snap raster to first raster (priority raster)
arcpy.env.snapRaster = raw_raster_list[0]

#--------------------------------------------

# 0.3 Check out spacial analyst extension
arcpy.CheckOutExtension('Spatial')

#--------------------------------------------------------------------------

# 1. Create Accuracy Fields Shapefile and Training Fields Shapefile, subset from Edited Fields Shapefile

# Create Accuracy Fields Shapefile 

region_and_time = os.path.basename(edited_field_borders_shapefile).rsplit(sep = '_', maxsplit = 1)[0]
accuracy_fields_shapefile = os.path.join(covs_path, region_and_time + '_accuracy_fields.shp')

# Add field delimiters to eliminate difference in SQL expression based on type of dataset being queried

aa_SQL_clause = """{} = {}""".format(arcpy.AddFieldDelimiters(edited_field_borders_shapefile, 'aa'), 2)
arcpy.Select_analysis(in_features = edited_field_borders_shapefile, out_feature_class = accuracy_fields_shapefile, where_clause = aa_SQL_clause)

arcpy.AddMessage('Generated Accuracy Fields Shapefile: ' + str(accuracy_fields_shapefile) + ' in ' + str(covs_path))

# Create Training Fields Shapefile 

training_fields_shapefile = os.path.join(covs_path, region_and_time + '_training_fields.shp')

# Add field delimiters to eliminate difference in SQL expression based on type of dataset being queried

tr_SQL_clause = """{} = {}""".format(arcpy.AddFieldDelimiters(edited_field_borders_shapefile, 'aa'), 1)
arcpy.Select_analysis(in_features = edited_field_borders_shapefile, out_feature_class = training_fields_shapefile, where_clause = tr_SQL_clause)

arcpy.AddMessage('Generated Training Fields Shapefile: ' + str(training_fields_shapefile) + ' in ' + str(covs_path))

#--------------------------------------------------------------------------

# 2. Create Training Fields Mask Shapefile, 30 meter inner buffer mask of Training Fields Shapefile

training_fields_mask = os.path.join(covs_path, region_and_time + '_training_fields_mask.shp')

arcpy.Buffer_analysis(in_features = training_fields_shapefile, out_feature_class = training_fields_mask, buffer_distance_or_field = '-30') 

arcpy.AddMessage('Generated Training Fields Mask: ' + str(training_fields_mask) + ' in ' + str(covs_path))

#--------------------------------------------------------------------------

# 3. Reproject rasters 

# Assign variable to name of spatial reference of Edited Field Borders Shapefile
borders_spatial_reference = arcpy.Describe(edited_field_borders_shapefile).spatialReference.name

arcpy.AddMessage('Edited Field Borders Shapefile has a projection of: ' + borders_spatial_reference)

# Create a list (used for mosaicing in next step) originally comprised of raw rasters that are replaced if necessary with reprojected ones 
raster_list = raw_raster_list

for (i, raster) in enumerate(raster_list):
    arcpy.AddMessage(raster + ' has a projection of: ' + arcpy.Describe(raster).spatialReference.name)
    
    # If the raster has a projection other than that of Edited Field Borders Shapefile, replace itself with a reprojected version 
    if arcpy.Describe(raster).spatialReference.name != borders_spatial_reference:
        arcpy.AddMessage('Projection of ' + raster + ' does not match that of Edited Field Borders Shapefile; reprojecting.')
        reprojected_raster = os.path.splitext(raster)[0] + '_' + borders_spatial_reference + '.img'
        
        # Check if pre-existing raster exists and delete if so
        if arcpy.Exists(reprojected_raster):
            arcpy.Delete_management(in_data = reprojected_raster)
            arcpy.AddMessage('Deleted pre-existing reprojected raster: ' + reprojected_raster)
        
        # Reproject raster
        arcpy.ProjectRaster_management(in_raster = raster, out_raster = reprojected_raster, out_coor_system = edited_field_borders_shapefile)
        arcpy.AddMessage('Generated: ' + reprojected_raster)
        
        # Replace original raster with that of reprojected raster
        raster_list[i] = reprojected_raster
    
    else:
        arcpy.AddMessage(raster + ' projection matches that of Edited Field Border Shapefile; reprojection not necessary.')
        
#--------------------------------------------------------------------------

# 4. Mosaic rasters (if applicable)

arcpy.env.snapRaster = raster_list[0]

# If there is more than one passed through GUI by user in Raw Image(s) multi-value parameter:
if len(raster_list) > 1:

    # Set Mosaiced Raw Image(s) name and path 
    mosaic_raster_name = os.path.splitext(raster_list[0])[0] + '_mosaic.img'
    mosaic_raster = os.path.join(img_path, mosaic_raster_name) 

    # Check for previously existing mosaic raster and delete if so as cannot be overwritten even with overwrite set to True
    
    if arcpy.Exists(mosaic_raster):
        arcpy.Delete_management(in_data = mosaic_raster)
        arcpy.AddMessage('Deleted pre-existing mosaic raster')

    # Check that all rasters to be mosaiced have same no data value
    
    # Create list comprehension of no data value of reprojected rasters
    no_data_list = [arcpy.Raster(b).noDataValue for b in raster_list]
    
    # If all no data values match, assign variable to this consistent no data value
    if len(set(no_data_list)) == 1:
        no_data_value = no_data_list[0]
        
        # Mosaic rasters if there is more than one
        arcpy.Mosaic_management(inputs = raster_list, target = raster_list[0], mosaic_type = 'FIRST', colormap = 'FIRST', nodata_value = no_data_value)
    
        # Try to rename first input raster as this is the file all others have been mosaiced to
        try:
            arcpy.Rename_management(in_data = raster_list[0], out_data = mosaic_raster_name)
        
        # If an exception is raised (ExecuteError: ERROR 000012: *mosaic.img already exists), and first input raster cannot be renamed, execute the following
        except Exception:
            
            arcpy.AddWarning('Cannot rename first input raster which is now a mosaic. After tool has completed running, please manually rename ' + raster_list[0] + ' to ' + mosaic_raster)
            
            for a in raster_list[1:]:
                
                # Keep first input raster so user can manually rename it; delete all other reprojected rasters
                arcpy.Delete_management(in_data = a)
                arcpy.AddMessage('Deleted intermediary raster: ' + a)
                
            # Assign variable to first input raster so that it is used as base for subsequent subsets
            raster = raster_list[0]
        
        # If an exception is not raised, execute the following
        else:
            arcpy.AddMessage('Generated new mosaic raster: ' + mosaic_raster_name)
            
            for r in raster_list:
                
                # Delete all intermediary rasters
                arcpy.Delete_management(in_data = r)
                arcpy.AddMessage('Deleted intermediary raster: ' + r)
                
        # Assign variable to mosaic raster
        raster = mosaic_raster 
    
    else:
        arcpy.AddError('No data values for input rasters were not consistent, please examine no data values of input rasters to ensure consistency before mosaicing')
        sys.exit(0)   
    
# If user only passes one raster, assign variable to the reprojected raster so that it is used as base for subsequent subsets 
else: 
    raster = raster_list[0] 
    
#--------------------------------------------------------------------------

# 5. Create three subsets from Mosaiced Raw Raster Image(s) or Raw Image 

# Reset snap raster environment parameter
arcpy.env.snapRaster = raster

# Generate bounding box, a square polygon that containsall polygons of edited field borders shapefile
bounding_box = os.path.join(covs_path, region_and_time + '_bounding_box.shp') 
arcpy.MinimumBoundingGeometry_management(in_features = edited_field_borders_shapefile, out_feature_class = bounding_box, geometry_type = 'ENVELOPE', group_option = 'ALL')

# Find extent of bounding box and raster 

describe_box = arcpy.Describe(bounding_box)
extent_box = describe_box.extent

describe_raster = arcpy.Describe(raster)
extent_raster = describe_raster.extent

box_contains_raster = extent_raster.contains(extent_box)

# Test whether bounding box extent is within raster; if so, subset raster 
if box_contains_raster == True:
    
    # Set path name and file name for AOI Subset Raster
    aoi_subset = os.path.join(img_path, region_and_time + '_AOI_subset.img')
    
    # Create AOI Subset Raster   
    arcpy.env.mask = bounding_box
    out_aoi_raster = ExtractByMask(in_raster = raster, in_mask_data = bounding_box)
    out_aoi_raster.save(aoi_subset)    
    del out_aoi_raster
    
    arcpy.AddMessage('Generated AOI Subset Raster: ' + aoi_subset)

    # Generate Field Borders Subset Raster
    
    # Create name and path for Field Borders Subset Raster
    fields_subset = os.path.join(img_path, region_and_time + '_fields_subset.img')
    
    # Create Field Borders Subset Raster    
    arcpy.env.mask = edited_field_borders_shapefile
    out_borders_raster = ExtractByMask(in_raster = raster, in_mask_data = edited_field_borders_shapefile)
    out_borders_raster.save(fields_subset)   
    del out_borders_raster
    
    arcpy.AddMessage('Generated Field Borders Subset Raster: ' + fields_subset)
    
    # Generate Training Fields Subset Raster
    
    # Create name and path for Training Fields Subset Raster
    training_subset = os.path.join(img_path, region_and_time + '_training_subset.img')
    
    # Create Training Fields Subset Raster
    arcpy.env.mask = training_fields_mask
    out_training_raster = ExtractByMask(in_raster = raster, in_mask_data = training_fields_mask)
    out_training_raster.save(training_subset)  
    del out_training_raster
    
    arcpy.AddMessage('Generated Training Subset Raster: ' + training_subset)

else: 
    arcpy.AddError('Raster does not fully contain a minimum bounding box of edited field borders feature class. Please include additional raster in Raw Images parameter.')
    sys.exit(0)    
