# -*- coding: utf-8 -*-
"""
Utility Functions
Helper functions for extracting context and formatting
"""

try:
    from Autodesk.Revit.DB import *
    from Autodesk.Revit.UI import *
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False

try:
    from pyrevit import revit, DB
except ImportError:
    pass

import base64
import io
import ctypes
import System.Diagnostics


def _safe_print(message):
    """Print message safely, handling Unicode errors in IronPython"""
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            print(message.encode('ascii', 'replace').decode('ascii'))
        except:
            pass

# Define RECT structure for Windows API
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

def get_revit_window_bounds():
    """
    Returns the bounding rectangle of the main Revit window.
    Returns: (x, y, width, height) or None if failed.
    """
    try:
        hwnd = None
        
        # 1. Try to get handle from pyrevit (most reliable)
        try:
            if 'revit' in globals() and hasattr(revit, 'uiapp'):
                hwnd = revit.uiapp.MainWindowHandle
        except Exception:
            pass
            
        # 2. Fallback to process main window if it looks like Revit
        if not hwnd:
            process = System.Diagnostics.Process.GetCurrentProcess()
            # Only use if title indicates it's Revit (avoids capturing plugin windows)
            if "Revit" in process.MainWindowTitle:
                hwnd = process.MainWindowHandle
        
        # Check if we got a valid handle
        if not hwnd or (hasattr(hwnd, 'ToInt64') and hwnd.ToInt64() == 0):
            return None
            
        # Handle IntPtr if needed
        hwnd_val = hwnd.ToInt64() if hasattr(hwnd, 'ToInt64') else hwnd

        # Prepare ctypes to call GetWindowRect from user32.dll
        user32 = ctypes.windll.user32
        rect = RECT()
        
        # Call the API
        result = user32.GetWindowRect(hwnd_val, ctypes.byref(rect))
        
        if result:
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            return (rect.left, rect.top, width, height)
            
    except Exception as e:
        _safe_print("Error getting window bounds: {}".format(str(e)))
        
    return None


def capture_revit_screenshot():
    """
    Capture a screenshot of the active Revit window
    
    Returns:
        str: Base64 encoded PNG image, or None if capture fails
    """
    try:
        import clr
        clr.AddReference('System.Drawing')
        clr.AddReference('System.Windows.Forms')
        
        import System
        from System.Windows import Forms
        from System.Drawing import Bitmap, Imaging
        from System.Drawing.Imaging import ImageFormat
        from System.IO import MemoryStream
        import time
        
        # Get Revit window bounds
        bounds_rect = get_revit_window_bounds()
        
        if bounds_rect:
            x, y, width, height = bounds_rect
            # Ensure valid dimensions
            if width <= 0 or height <= 0:
                # Fallback to primary screen
                screen = Forms.Screen.PrimaryScreen
                x, y = 0, 0
                width, height = screen.Bounds.Width, screen.Bounds.Height
        else:
            # Fallback to primary screen
            screen = Forms.Screen.PrimaryScreen
            x, y = 0, 0
            width, height = screen.Bounds.Width, screen.Bounds.Height
        
        # Retry logic for clipboard conflicts
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                # Create bitmap and capture screen
                bitmap = Bitmap(width, height)
                graphics = System.Drawing.Graphics.FromImage(bitmap)
                graphics.CopyFromScreen(x, y, 0, 0, bitmap.Size)
                
                # Convert to base64
                stream = MemoryStream()
                bitmap.Save(stream, ImageFormat.Png)
                stream.Position = 0
                
                # Read bytes and convert to base64
                byte_array = stream.ToArray()
                base64_string = base64.b64encode(bytes(byte_array)).decode('utf-8')
                
                # Cleanup
                graphics.Dispose()
                bitmap.Dispose()
                stream.Dispose()
                
                return base64_string
                
            except System.Runtime.InteropServices.COMException as e:
                # Clipboard conflict - retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    _safe_print("Screenshot capture failed after {} retries: {}".format(max_retries, str(e)))
                    return None
        
        return None
        
    except Exception as e:
        _safe_print("Error capturing screenshot: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return None


def extract_revit_context():
    """
    Extract relevant context from current Revit session
    
    Returns:
        dict: Dictionary of context information
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        doc = revit.doc
        uidoc = revit.uidoc
        active_view = revit.active_view
        
        context = {}
        
        # Document info
        if doc:
            context['project_name'] = doc.Title or 'Untitled'
            context['revit_version'] = doc.Application.VersionNumber
            context['username'] = doc.Application.Username
            
        # Active view info
        if active_view:
            context['active_view'] = active_view.Name
            context['view_type'] = active_view.ViewType.ToString()
            
            # View template if any
            view_template_id = active_view.ViewTemplateId
            if view_template_id != DB.ElementId.InvalidElementId:
                template = doc.GetElement(view_template_id)
                if template:
                    context['view_template'] = template.Name
        
        # Current workset if applicable
        if doc.IsWorkshared:
            try:
                active_workset = doc.GetWorksetTable().GetActiveWorksetId()
                workset = doc.GetWorksetTable().GetWorkset(active_workset)
                context['active_workset'] = workset.Name
            except:
                pass
        
        # Selection info
        if uidoc:
            selection = uidoc.Selection
            selected_ids = selection.GetElementIds()
            
            if selected_ids.Count > 0:
                context['selection_count'] = selected_ids.Count
                context['selected_elements'] = []
                
                # Extract detailed info from first 10 selected elements
                for elem_id in list(selected_ids)[:10]:
                    element = doc.GetElement(elem_id)
                    if element:
                        elem_info = _extract_element_details(element, doc)
                        if elem_info:
                            context['selected_elements'].append(elem_info)
                
                # Indicate if selection was truncated
                if selected_ids.Count > 10:
                    context['selection_truncated'] = True
        
        return context if context else None
        
    except Exception as e:
        # If any error extracting context, return None
        _safe_print("Error extracting Revit context: {}".format(str(e)))
        return None


def _extract_element_details(element, doc):
    """
    Extract comprehensive information from a single element including ALL parameters
    
    Args:
        element: Revit element
        doc: Revit document
        
    Returns:
        dict: Element details with all parameters
    """
    try:
        info = {
            'id': element.Id.IntegerValue,
            'category': element.Category.Name if element.Category else 'No Category',
        }
        
        # Try to get element name safely
        try:
            if hasattr(element, 'Name'):
                name = element.Name
                if name:
                    info['name'] = name
        except:
            pass
        
        # Element type information
        try:
            type_id = element.GetTypeId()
            if type_id != DB.ElementId.InvalidElementId:
                elem_type = doc.GetElement(type_id)
                if elem_type:
                    try:
                        info['type_name'] = elem_type.Name
                    except:
                        pass
                    
                    try:
                        if hasattr(elem_type, 'FamilyName'):
                            info['family_name'] = elem_type.FamilyName
                    except:
                        pass
                    
                    # Extract ALL type parameters
                    try:
                        type_params = _extract_all_parameters(elem_type, doc)
                        if type_params:
                            info['type_parameters'] = type_params
                    except:
                        pass
        except:
            pass
        
        # Workset information
        if doc.IsWorkshared:
            try:
                workset_id = element.WorksetId
                if workset_id != DB.WorksetId.InvalidWorksetId:
                    workset = doc.GetWorksetTable().GetWorkset(workset_id)
                    info['workset'] = workset.Name
            except:
                pass
        
        # Level
        try:
            level_param = element.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM)
            if not level_param:
                level_param = element.get_Parameter(DB.BuiltInParameter.SCHEDULE_LEVEL_PARAM)
            
            if level_param and level_param.HasValue:
                level_id = level_param.AsElementId()
                if level_id != DB.ElementId.InvalidElementId:
                    level = doc.GetElement(level_id)
                    if level:
                        info['level'] = level.Name
        except:
            pass
        
        # Phase Created
        try:
            phase_created = element.get_Parameter(DB.BuiltInParameter.PHASE_CREATED)
            if phase_created and phase_created.HasValue:
                phase_id = phase_created.AsElementId()
                phase = doc.GetElement(phase_id)
                if phase:
                    info['phase_created'] = phase.Name
        except:
            pass
        
        # Design option
        try:
            design_option = element.DesignOption
            if design_option:
                info['design_option'] = design_option.Name
        except:
            pass
        
        # Extract ALL instance parameters
        try:
            instance_params = _extract_all_parameters(element, doc)
            if instance_params:
                info['parameters'] = instance_params
        except:
            pass
        
        return info
        
    except Exception as e:
        _safe_print("Error extracting element details: {}".format(str(e)))
        return None


def _extract_all_parameters(element, doc):
    """
    Extract ALL parameters from an element (not just key ones)
    
    Args:
        element: Revit element
        doc: Revit document
        
    Returns:
        dict: All parameter names and values
    """
    params = {}
    
    try:
        for param in element.Parameters:
            if param and param.HasValue:
                param_name = param.Definition.Name
                param_value = _get_parameter_value(param, doc)
                
                if param_value is not None:
                    # Group by parameter type for better organization
                    param_info = {
                        'value': param_value,
                        'type': param.StorageType.ToString(),
                    }
                    
                    # Add read-only status
                    if param.IsReadOnly:
                        param_info['read_only'] = True
                    
                    # Add shared parameter info
                    if param.IsShared:
                        param_info['shared'] = True
                    
                    params[param_name] = param_info
    
    except Exception as e:
        _safe_print("Error extracting parameters: {}".format(str(e)))
    
    return params


def _get_parameter_value(parameter, doc):
    """
    Get parameter value as string with proper formatting and Unicode handling
    
    Args:
        parameter: Revit parameter
        doc: Revit document
        
    Returns:
        str: Formatted parameter value
    """
    try:
        storage_type = parameter.StorageType
        
        if storage_type == DB.StorageType.String:
            value = parameter.AsString()
            if value:
                # Replace problematic Unicode characters
                try:
                    return value.encode('utf-8', 'replace').decode('utf-8')
                except:
                    return str(value)
            return value
            
        elif storage_type == DB.StorageType.Integer:
            # Check if it's an enumeration
            try:
                as_value_string = parameter.AsValueString()
                if as_value_string:
                    return as_value_string.encode('utf-8', 'replace').decode('utf-8')
            except:
                pass
            return str(parameter.AsInteger())
            
        elif storage_type == DB.StorageType.Double:
            # Use AsValueString() for proper unit display
            try:
                as_value_string = parameter.AsValueString()
                if as_value_string:
                    return as_value_string.encode('utf-8', 'replace').decode('utf-8')
            except:
                pass
            return "{:.3f}".format(parameter.AsDouble())
            
        elif storage_type == DB.StorageType.ElementId:
            elem_id = parameter.AsElementId()
            if elem_id != DB.ElementId.InvalidElementId:
                elem = doc.GetElement(elem_id)
                if elem:
                    try:
                        name = elem.Name
                        return name.encode('utf-8', 'replace').decode('utf-8')
                    except:
                        return "Element_{}".format(elem_id.IntegerValue)
                if elem:
                    return elem.Name
            return None
        
        # Fallback to AsValueString
        return parameter.AsValueString()
        
    except Exception as e:
        _safe_print("Error getting parameter value: {}".format(str(e)))
        return None


def format_markdown(text):
    """
    Format markdown-style text for WPF display
    (Basic implementation - can be enhanced)
    """
    # This is a placeholder - would need more robust markdown parsing
    # For now, just return the text as-is
    return text


def truncate_text(text, max_length=500):
    """Truncate text to max length with ellipsis"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
