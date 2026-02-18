# -*- coding: utf-8 -*-
"""
Revit Actions Module
Enables the chatbot to perform actions in Revit
"""

try:
    from Autodesk.Revit.DB import *
    from Autodesk.Revit.UI import *
    from pyrevit import revit, DB, forms
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False

import json
import re
import re


class ActionEventHandler(IExternalEventHandler):
    """Handler for executing actions through ExternalEvent"""
    
    def __init__(self):
        self.action_data = None
        self.result = None
        self.executor = None
        self.callback = None
    
    def Execute(self, uiapp):
        """Execute the action in Revit's API context"""
        try:
            if self.executor and self.action_data:
                self.result = self.executor._execute_action_internal(self.action_data)
            else:
                self.result = {'success': False, 'message': 'No action data'}
        except Exception as e:
            import traceback
            error_msg = 'Error: {}\n{}'.format(str(e), traceback.format_exc())
            self.result = {'success': False, 'message': error_msg}
        
        # Call callback if provided
        if self.callback:
            try:
                self.callback(self.result)
            except:
                pass
    
    def GetName(self):
        return "ChatActionEventHandler"


class RevitActionExecutor:
    """Execute actions in Revit based on chatbot suggestions"""
    
    def __init__(self, doc, uidoc):
        self.doc = doc
        self.uidoc = uidoc
        
        # Create external event handler for thread-safe execution
        self.event_handler = ActionEventHandler()
        self.event_handler.executor = self
        self.external_event = ExternalEvent.Create(self.event_handler)
    
    def execute_action(self, action_data, callback=None):
        """
        Execute a Revit action based on action data using ExternalEvent
        Supports both single actions and action workflows (arrays of actions)
        
        Args:
            action_data (dict or list): Action definition or list of actions for workflow
            callback (function): Optional callback function to receive result
            
        Returns:
            dict: Result of the action (or None if callback is used)
        """
        # Check if this is a workflow (list of actions)
        if isinstance(action_data, list):
            return self.execute_workflow(action_data, callback)
        
        # Store action data and callback in handler
        self.event_handler.action_data = action_data
        self.event_handler.result = None
        self.event_handler.callback = callback
        
        # Raise the external event to execute in Revit API context
        status = self.external_event.Raise()
        
        # If callback provided, return immediately
        if callback:
            return None
        
        # Otherwise wait for result (with timeout)
        import time
        timeout = 10  # seconds
        elapsed = 0
        while self.event_handler.result is None and elapsed < timeout:
            time.sleep(0.1)
            elapsed += 0.1
        
        if self.event_handler.result is None:
            return {
                'success': False,
                'message': 'Action timed out'
            }
        
        return self.event_handler.result
    
    def execute_workflow(self, actions, callback=None):
        """
        Execute a series of actions in sequence, with conditional execution
        
        Args:
            actions (list): List of action definitions
            callback (function): Optional callback function to receive final result
            
        Returns:
            dict: Result with success status and details of each step
        """
        # Package workflow as special action type to execute in single ExternalEvent
        workflow_action = {
            'type': 'workflow',
            'workflow': actions
        }
        
        # Execute through normal action execution (single ExternalEvent)
        self.event_handler.action_data = workflow_action
        self.event_handler.result = None
        self.event_handler.callback = callback
        
        status = self.external_event.Raise()
        
        # If callback provided, return immediately
        if callback:
            return None
        
        # Otherwise wait for result (with timeout)
        import time
        timeout = 30  # Longer timeout for workflows
        elapsed = 0
        while self.event_handler.result is None and elapsed < timeout:
            time.sleep(0.1)
            elapsed += 0.1
        
        if self.event_handler.result is None:
            return {
                'success': False,
                'message': 'Workflow timed out'
            }
        
        return self.event_handler.result
    
    def _execute_workflow_internal(self, actions):
        """
        Execute workflow actions internally (within ExternalEvent context)
        This runs all steps in sequence within a single Revit API transaction context
        """
        results = []
        workflow_context = {}  # Share data between actions
        
        for i, action_data in enumerate(actions):
            # Substitute variables from previous results
            action_data = self._substitute_workflow_variables(action_data, workflow_context)
            
            # Check if action has a condition based on previous result
            condition = action_data.get('condition')
            if condition:
                # Skip if condition not met
                if condition == 'if_previous_failed' and results and results[-1]['success']:
                    continue
                elif condition == 'if_previous_succeeded' and results and not results[-1]['success']:
                    continue
            
            # Execute action directly (we're already in ExternalEvent context)
            result = self._execute_action_internal(action_data)
            results.append(result)
            
            # Update workflow context with result data
            if result.get('success'):
                workflow_context.update(result)
            
            # Stop workflow if action failed and no error handling specified
            if not result['success'] and not action_data.get('continue_on_error', False):
                break
        
        # Prepare final result
        return {
            'success': all(r['success'] for r in results),
            'message': 'Completed {} of {} actions'.format(
                sum(1 for r in results if r['success']), 
                len(results)
            ),
            'steps': results
        }
    
    def _substitute_workflow_variables(self, action_data, context):
        """
        Replace {{variable}} placeholders in action parameters with values from context
        
        Args:
            action_data (dict): Action definition with possible {{variable}} placeholders
            context (dict): Context with variable values
            
        Returns:
            dict: Action data with variables substituted
        """
        import copy
        action_data = copy.deepcopy(action_data)
        
        # Substitute in params
        if 'params' in action_data:
            for key, value in action_data['params'].items():
                if isinstance(value, str) and '{{' in value and '}}' in value:
                    # Extract variable name
                    var_match = re.search(r'\{\{(\w+)\}\}', value)
                    if var_match:
                        var_name = var_match.group(1)
                        if var_name in context:
                            action_data['params'][key] = context[var_name]
        
        return action_data
    
    def _execute_action_internal(self, action_data):
        """
        Internal method that actually executes the action
        This runs in Revit's API context via ExternalEvent
        """
        action_type = action_data.get('type')
        params = action_data.get('params', {})
        
        try:
            # Handle workflow execution
            if action_type == 'workflow':
                return self._execute_workflow_internal(action_data.get('workflow', []))
            
            elif action_type == 'select_elements':
                return self._select_elements(params)
            
            elif action_type == 'deselect_all':
                return self._deselect_all(params)
            
            elif action_type == 'determine_workset':
                return self._determine_workset(params)
            
            elif action_type == 'update_parameters':
                return self._update_parameters(params)
            
            elif action_type == 'apply_view_template':
                return self._apply_view_template(params)
            
            elif action_type == 'change_workset':
                return self._change_workset(params)
            
            elif action_type == 'create_workset':
                return self._create_workset(params)
            
            elif action_type == 'isolate_elements':
                return self._isolate_elements(params)
            
            elif action_type == 'check_standards':
                return self._check_standards(params)
            
            else:
                return {
                    'success': False,
                    'message': 'Unknown action type: {}'.format(action_type)
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': 'Error executing action: {}'.format(str(e))
            }
    
    def _select_elements(self, params):
        """Select elements based on criteria"""
        category_name = params.get('category')
        param_filter = params.get('parameter_filter')
        workset_name = params.get('workset')
        
        # Build filter
        elements = []
        
        if category_name:
            # Get category
            category = None
            for cat in self.doc.Settings.Categories:
                if cat.Name == category_name:
                    category = cat
                    break
            
            if category:
                collector = FilteredElementCollector(self.doc) \
                    .OfCategoryId(category.Id) \
                    .WhereElementIsNotElementType()
                
                elements = list(collector)
        
        # Filter by parameter if specified
        if param_filter and elements:
            param_name = param_filter.get('name')
            param_value = param_filter.get('value')
            condition = param_filter.get('condition', 'equals')
            
            filtered = []
            for elem in elements:
                param = elem.LookupParameter(param_name)
                
                # Handle different conditions
                if condition == 'is_empty':
                    # Check if parameter is empty/missing
                    if not param or not param.HasValue or not param.AsString():
                        filtered.append(elem)
                elif condition == 'equals':
                    # Check if parameter equals value
                    if param and param.HasValue:
                        if str(param.AsValueString()) == str(param_value):
                            filtered.append(elem)
                elif condition == 'contains':
                    # Check if parameter contains value
                    if param and param.HasValue:
                        param_str = str(param.AsString() or param.AsValueString() or '')
                        if param_value.lower() in param_str.lower():
                            filtered.append(elem)
            
            elements = filtered
        
        # Filter by workset if specified
        if workset_name and self.doc.IsWorkshared and elements:
            filtered = []
            for elem in elements:
                workset_id = elem.WorksetId
                if workset_id != WorksetId.InvalidWorksetId:
                    workset = self.doc.GetWorksetTable().GetWorkset(workset_id)
                    if workset.Name == workset_name:
                        filtered.append(elem)
            
            elements = filtered
        
        # Select the elements
        if elements:
            import System.Collections.Generic
            element_ids = [elem.Id for elem in elements]
            self.uidoc.Selection.SetElementIds(
                System.Collections.Generic.List[ElementId](element_ids)
            )
            
            return {
                'success': True,
                'message': 'Selected {} elements'.format(len(elements)),
                'count': len(elements)
            }
        else:
            return {
                'success': False,
                'message': 'No elements found matching criteria'
            }
    
    def _deselect_all(self, params):
        """Deselect all elements"""
        try:
            import System.Collections.Generic
            empty_list = System.Collections.Generic.List[ElementId]()
            self.uidoc.Selection.SetElementIds(empty_list)
            
            return {
                'success': True,
                'message': 'Deselected all elements'
            }
        except Exception as e:
            return {
                'success': False,
                'message': 'Error deselecting: {}'.format(str(e))
            }
    
    def _determine_workset(self, params):
        """
        Analyze selected element(s) and determine appropriate workset based on category
        Returns the recommended workset name and whether it exists
        """
        selection = self.uidoc.Selection.GetElementIds()
        
        if not selection or selection.Count == 0:
            return {
                'success': False,
                'message': 'No elements selected'
            }
        
        # Get first selected element
        first_elem = self.doc.GetElement(list(selection)[0])
        
        if not first_elem:
            return {
                'success': False,
                'message': 'Could not access selected element'
            }
        
        # Determine workset based on category
        category = first_elem.Category
        if not category:
            return {
                'success': False,
                'message': 'Element has no category'
            }
        
        category_name = category.Name
        
        # Map common categories to BBB workset conventions
        workset_mapping = {
            'Doors': 'A-DOOR',
            'Windows': 'A-GLAZ',
            'Walls': 'A-WALL',
            'Floors': 'A-FLOR',
            'Roofs': 'A-ROOF',
            'Ceilings': 'A-CLNG',
            'Stairs': 'A-STRS',
            'Railings': 'A-RAIL',
            'Furniture': 'A-FURN',
            'Casework': 'A-CASE',
            'Plumbing Fixtures': 'P-PLBG-FIXT',
            'Mechanical Equipment': 'M-HVAC-EQUP',
            'Lighting Fixtures': 'E-LITE',
            'Electrical Equipment': 'E-ELEC-EQUP',
            'Structural Columns': 'S-COLS',
            'Structural Framing': 'S-FRAM',
            'Generic Models': 'A-MODL',
            'Rooms': 'A-AREA-ROOM',
            'Areas': 'A-AREA'
        }
        
        recommended_workset = workset_mapping.get(category_name, 'A-MODL')
        
        # Check if workset exists
        workset_exists = False
        if self.doc.IsWorkshared:
            collector = FilteredWorksetCollector(self.doc)
            collector.OfKind(WorksetKind.UserWorkset)
            
            for workset in collector:
                if workset.Name == recommended_workset:
                    workset_exists = True
                    break
        
        return {
            'success': True,
            'message': 'Element category: {}. Recommended workset: {}'.format(
                category_name, recommended_workset
            ),
            'category': category_name,
            'recommended_workset': recommended_workset,
            'workset_exists': workset_exists,
            'selection_count': selection.Count
        }
    
    def _update_parameters(self, params):
        """Update parameters on selected elements"""
        param_name = params.get('parameter_name')
        param_value = params.get('parameter_value')
        
        selection = self.uidoc.Selection.GetElementIds()
        
        if not selection or selection.Count == 0:
            return {
                'success': False,
                'message': 'No elements selected'
            }
        
        # Use pyRevit transaction context
        try:
            with revit.Transaction('Update Parameters'):
                updated_count = 0
                
                for elem_id in selection:
                    elem = self.doc.GetElement(elem_id)
                    param = elem.LookupParameter(param_name)
                    
                    if param and not param.IsReadOnly:
                        # Set value based on storage type
                        storage_type = param.StorageType
                        
                        if storage_type == StorageType.String:
                            param.Set(str(param_value))
                            updated_count += 1
                        elif storage_type == StorageType.Integer:
                            param.Set(int(param_value))
                            updated_count += 1
                        elif storage_type == StorageType.Double:
                            param.Set(float(param_value))
                            updated_count += 1
                
                return {
                    'success': True,
                    'message': 'Updated parameter "{}" on {} elements'.format(
                        param_name, updated_count
                    ),
                    'count': updated_count
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': 'Error updating parameters: {}'.format(str(e))
            }
    
    def _change_workset(self, params):
        """Change workset of selected elements"""
        # Check if document can be modified
        if self.doc.IsReadOnly:
            return {
                'success': False,
                'message': 'Document is read-only'
            }
        
        if not self.doc.IsWorkshared:
            return {
                'success': False,
                'message': 'Model is not workshared'
            }
        
        workset_name = params.get('workset_name')
        selection = self.uidoc.Selection.GetElementIds()
        
        if not selection or selection.Count == 0:
            return {
                'success': False,
                'message': 'No elements selected'
            }
        
        # Find workset by iterating through workset IDs
        workset_table = self.doc.GetWorksetTable()
        target_workset = None
        
        # Get all user worksets
        collector = FilteredWorksetCollector(self.doc)
        collector.OfKind(WorksetKind.UserWorkset)
        
        for workset_id in collector.ToWorksetIds():
            workset = workset_table.GetWorkset(workset_id)
            if workset.Name == workset_name:
                target_workset = workset
                break
        
        if not target_workset:
            return {
                'success': False,
                'message': 'Workset "{}" not found'.format(workset_name)
            }
        
        # Check if target workset is editable
        if not target_workset.IsEditable:
            return {
                'success': False,
                'message': 'Workset "{}" is not editable. It may be owned/borrowed by another user. Try relinquishing and borrowing the workset first.'.format(workset_name)
            }
        
        # Use pyRevit transaction context
        try:
            with revit.Transaction('Change Workset'):
                changed_count = 0
                
                for elem_id in selection:
                    elem = self.doc.GetElement(elem_id)
                    
                    # Check if element can be assigned to workset
                    if hasattr(elem, 'WorksetId'):
                        workset_param = elem.get_Parameter(
                            BuiltInParameter.ELEM_PARTITION_PARAM
                        )
                        
                        if workset_param and not workset_param.IsReadOnly:
                            workset_param.Set(target_workset.Id.IntegerValue)
                            changed_count += 1
                
                return {
                    'success': True,
                    'message': 'Moved {} elements to workset "{}"'.format(
                        changed_count, workset_name
                    ),
                    'count': changed_count
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': 'Error changing workset: {}'.format(str(e))
            }
    
    def _create_workset(self, params):
        """Create a new workset"""
        workset_name = params.get('workset_name')
        
        # Check if document is workshared
        if not self.doc.IsWorkshared:
            return {
                'success': False,
                'message': 'Document is not workshared. Enable worksharing first.'
            }
        
        # Check if document can be modified
        if self.doc.IsReadOnly:
            return {
                'success': False,
                'message': 'Document is read-only'
            }
        
        # Check if workset already exists
        collector = FilteredWorksetCollector(self.doc)
        collector.OfKind(WorksetKind.UserWorkset)
        
        for workset in collector:
            if workset.Name == workset_name:
                return {
                    'success': False,
                    'message': 'Workset "{}" already exists'.format(workset_name)
                }
        
        # Create the workset
        try:
            with revit.Transaction('Create Workset'):
                new_workset = Workset.Create(self.doc, workset_name)
                
                return {
                    'success': True,
                    'message': 'Created workset "{}"'.format(workset_name)
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': 'Error creating workset: {}'.format(str(e))
            }
    
    def _apply_view_template(self, params):
        """Apply view template to active view"""
        template_name = params.get('template_name')
        
        active_view = self.doc.ActiveView
        
        if not active_view or active_view.IsTemplate:
            return {
                'success': False,
                'message': 'No valid view active'
            }
        
        # Find template
        templates = FilteredElementCollector(self.doc) \
            .OfClass(View) \
            .ToElements()
        
        target_template = None
        for template in templates:
            if template.IsTemplate and template.Name == template_name:
                target_template = template
                break
        
        if not target_template:
            return {
                'success': False,
                'message': 'View template "{}" not found'.format(template_name)
            }
        
        # Apply template
        try:
            with revit.Transaction('Apply View Template'):
                active_view.ViewTemplateId = target_template.Id
                
                return {
                    'success': True,
                    'message': 'Applied template "{}" to view "{}"'.format(
                        template_name, active_view.Name
                    )
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': 'Error applying template: {}'.format(str(e))
            }
    
    def _isolate_elements(self, params):
        """Isolate elements in active view"""
        selection = self.uidoc.Selection.GetElementIds()
        
        if not selection or selection.Count == 0:
            return {
                'success': False,
                'message': 'No elements selected'
            }
        
        active_view = self.doc.ActiveView
        
        try:
            with revit.Transaction('Isolate Elements'):
                active_view.IsolateElementsTemporary(selection)
                
                return {
                    'success': True,
                    'message': 'Isolated {} elements in current view'.format(
                        selection.Count
                    )
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': 'Error isolating elements: {}'.format(str(e))
            }
    
    def _check_standards(self, params):
        """Check selected elements against standards"""
        check_type = params.get('check_type', 'all')
        selection = self.uidoc.Selection.GetElementIds()
        
        if not selection or selection.Count == 0:
            return {
                'success': False,
                'message': 'No elements selected'
            }
        
        issues = []
        
        for elem_id in selection:
            elem = self.doc.GetElement(elem_id)
            
            # Check workset naming
            if check_type in ['all', 'workset']:
                if self.doc.IsWorkshared:
                    workset_id = elem.WorksetId
                    if workset_id != WorksetId.InvalidWorksetId:
                        workset = self.doc.GetWorksetTable().GetWorkset(workset_id)
                        
                        # Example check: Workset should start with discipline
                        valid_prefixes = ['A-', 'S-', 'MEP-', 'C-']
                        if not any(workset.Name.startswith(p) for p in valid_prefixes):
                            issues.append({
                                'element_id': elem_id.IntegerValue,
                                'category': elem.Category.Name if elem.Category else 'Unknown',
                                'issue': 'Invalid workset name: {}'.format(workset.Name),
                                'workset': workset.Name
                            })
            
            # Check for required parameters
            if check_type in ['all', 'parameters']:
                required_params = ['Mark', 'Comments']
                
                for param_name in required_params:
                    param = elem.LookupParameter(param_name)
                    if not param or not param.HasValue or not param.AsString():
                        issues.append({
                            'element_id': elem_id.IntegerValue,
                            'category': elem.Category.Name if elem.Category else 'Unknown',
                            'issue': 'Missing required parameter: {}'.format(param_name)
                        })
        
        return {
            'success': True,
            'message': 'Found {} standards issues'.format(len(issues)),
            'issues': issues,
            'count': len(issues)
        }


def parse_action_from_response(response_text):
    """
    Parse action suggestions from Claude's response
    Looks for JSON blocks with action definitions or workflows
    
    Args:
        response_text (str): Claude's response text
        
    Returns:
        list: List of action definitions (or single workflow item)
    """
    actions = []
    
    # Look for JSON code blocks in response
    json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    
    for json_str in json_blocks:
        try:
            action_data = json.loads(json_str)
            
            # Check for single action
            if 'action' in action_data:
                actions.append(action_data['action'])
            
            # Check for workflow (array of actions)
            elif 'workflow' in action_data:
                # Return workflow as a special action type that will be handled differently
                actions.append({
                    'type': 'workflow',
                    'label': 'Execute Workflow',
                    'description': 'Multi-step workflow',
                    'workflow': action_data['workflow']
                })
        except Exception as e:
            continue
    
    return actions

