import json
import boto3
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key
from decimal import Decimal

# Custom JSON encoder to handle Decimal objects
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'LeaveManagementTable'))

def apply_leave(employee_id, start_date, end_date, leave_type):
    """
    Apply for a leave
    
    Args:
        employee_id (int): ID of the employee applying for leave
        start_date (str): Start date of the leave (YYYY-MM-DD)
        end_date (str): End date of the leave (YYYY-MM-DD)
        leave_type (str): Type of leave (e.g., Annual, Sick, Personal)
        
    Returns:
        dict: Leave request details
    """
    try:
        # Get the employee record
        response = table.get_item(
            Key={
                'id': employee_id,
                'type': 'EMPLOYEE'
            }
        )
        
        if 'Item' not in response:
            return {
                'success': False,
                'message': f"Employee with ID {employee_id} not found"
            }
        
        employee = response['Item']
        
        # Check if leave type exists and employee has sufficient balance
        if 'leaveBalances' not in employee or leave_type not in employee['leaveBalances']:
            return {
                'success': False,
                'message': f"Leave type {leave_type} not found in employee's leave balances"
            }
        
        # Calculate duration in days
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        duration = (end_date_obj - start_date_obj).days + 1  # Include both start and end dates
        
        # Check if employee has sufficient leave balance
        current_balance = employee['leaveBalances'][leave_type]
        if current_balance < duration:
            return {
                'success': False,
                'message': f"Insufficient leave balance. Available: {current_balance}, Required: {duration}"
            }
        
        # Generate a unique leave ID
        timestamp = int(datetime.now().timestamp())
        leave_id = int(f"{employee_id}{timestamp % 10000}")
        
        # Create the leave request
        leave_request = {
            'id': leave_id,
            'type': 'LEAVE_REQUEST',
            'employeeId': employee_id,
            'employeeName': employee.get('name', 'Unknown'),
            'startDate': start_date,
            'endDate': end_date,
            'leaveType': leave_type,
            'duration': duration,
            'status': 'PENDING',
            'appliedAt': datetime.now().isoformat()
        }
        
        # Save the leave request to DynamoDB
        table.put_item(Item=leave_request)
        
        return {
            'success': True,
            'message': f"Leave request submitted successfully",
            'leaveId': leave_id,
            'status': 'PENDING',
            'duration': duration,
            'leaveType': leave_type,
            'availableBalance': current_balance
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error applying for leave: {str(e)}"
        }

def cancel_leave(leave_id=None, employee_id=None, leave_type=None, start_date=None):
    """
    Cancel a leave request
    
    Args:
        leave_id (int, optional): ID of the leave request to cancel
        employee_id (int, optional): ID of the employee
        leave_type (str, optional): Type of leave
        start_date (str, optional): Start date of the leave (YYYY-MM-DD)
        
    Returns:
        dict: Updated leave request details
    """
    try:
        leave_request = None
        
        # If leave_id is provided, use it to find the leave request
        if leave_id is not None:
            response = table.get_item(
                Key={
                    'id': leave_id,
                    'type': 'LEAVE_REQUEST'
                }
            )
            
            if 'Item' in response:
                leave_request = response['Item']
        
        # If leave_id is not provided but employee_id and leave_type are provided
        elif employee_id is not None and leave_type is not None and start_date is not None:
            # Query leave requests for this employee with the specified leave type and start date
            scan_response = table.scan(
                FilterExpression=Key('type').eq('LEAVE_REQUEST') & 
                                Key('employeeId').eq(employee_id) & 
                                Key('leaveType').eq(leave_type) & 
                                Key('startDate').eq(start_date)
            )
            
            leaves = scan_response.get('Items', [])
            
            # Get the most recent leave request if multiple exist
            if leaves:
                leaves.sort(key=lambda x: x.get('appliedAt', ''), reverse=True)
                leave_request = leaves[0]
                leave_id = leave_request['id']
        
        if leave_request is None:
            return {
                'success': False,
                'message': "Leave request not found. Please provide valid leave details."
            }
        
        # Check if leave can be cancelled
        if leave_request['status'] == 'CANCELLED':
            return {
                'success': False,
                'message': f"Leave request is already cancelled"
            }
        
        # Store the previous status to check if it was approved
        previous_status = leave_request['status']
        
        # Update the leave request status
        # Import timezone from datetime to create aware datetime objects
        from datetime import timezone  # Used to create timezone-aware datetime objects for accurate timestamp representation
        table.update_item(
            Key={
                'id': leave_id,
                'type': 'LEAVE_REQUEST'
            },
            UpdateExpression="SET #status = :status, cancelledAt = :cancelledAt",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'CANCELLED',
                ':cancelledAt': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # If the leave was previously approved, restore the leave balance
        if previous_status == 'APPROVED':
            employee_id = leave_request['employeeId']
            leave_type = leave_request['leaveType']
            duration = leave_request.get('duration', 1)  # Default to 1 day if duration not specified
            
            # Get the employee record
            employee_response = table.get_item(
                Key={
                    'id': employee_id,
                    'type': 'EMPLOYEE'
                }
            )
            
            if 'Item' in employee_response:
                employee = employee_response['Item']
                
                if 'leaveBalances' in employee and leave_type in employee['leaveBalances']:
                    current_balance = employee['leaveBalances'][leave_type]
                    new_balance = current_balance + duration
                    
                    # Update the employee's leave balance
                    table.update_item(
                        Key={
                            'id': employee_id,
                            'type': 'EMPLOYEE'
                        },
                        UpdateExpression="SET leaveBalances.#leaveType = :newBalance",
                        ExpressionAttributeNames={
                            '#leaveType': leave_type
                        },
                        ExpressionAttributeValues={
                            ':newBalance': new_balance
                        }
                    )
                    
                    return {
                        'success': True,
                        'message': f"Leave request with ID {leave_id} has been cancelled. Restored {duration} days to {leave_type} leave balance.",
                        'leaveId': leave_id,
                        'leaveType': leave_type,
                        'newBalance': new_balance
                    }
        
        return {
            'success': True,
            'message': f"Leave request with ID {leave_id} has been cancelled",
            'leaveId': leave_id
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error cancelling leave: {str(e)}"
        }

def get_leave_balance(employee_id):
    """
    Get leave balance for an employee
    
    Args:
        employee_id (int): ID of the employee
        
    Returns:
        dict: Employee's leave balance information
    """
    try:
        # Get the employee record
        response = table.get_item(
            Key={
                'id': employee_id,
                'type': 'EMPLOYEE'
            }
        )
        
        if 'Item' not in response:
            return {
                'success': False,
                'message': f"Employee with ID {employee_id} not found"
            }
        
        employee = response['Item']
        
        # Extract leave balances
        if 'leaveBalances' in employee:
            return {
                'success': True,
                'message': "Leave balances retrieved successfully",
                'employeeName': employee.get('name', 'Unknown'),
                'employeeId': employee_id,
                'department': employee.get('department', 'N/A'),
                'leaveBalances': employee['leaveBalances']
            }
        else:
            return {
                'success': True,
                'message': "Leave balances retrieved successfully",
                'employeeName': employee.get('name', 'Unknown'),
                'employeeId': employee_id,
                'department': employee.get('department', 'N/A'),
                'leaveBalances': {'Annual': employee.get('leaveBalance', 0)}
            }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error retrieving leave balance: {str(e)}"
        }

def get_leave_status(employee_id=None, leave_id=None):
    """
    Get leave status for an employee or a specific leave request
    
    Args:
        employee_id (int, optional): ID of the employee
        leave_id (int, optional): ID of the specific leave request
        
    Returns:
        dict: Leave status information
    """
    try:
        if leave_id is not None:
            # Get a specific leave request
            response = table.get_item(
                Key={
                    'id': leave_id,
                    'type': 'LEAVE_REQUEST'
                }
            )
            
            if 'Item' not in response:
                return {
                    'success': False,
                    'message': f"Leave request with ID {leave_id} not found"
                }
            
            leave_request = response['Item']
            
            return {
                'success': True,
                'message': "Leave request retrieved successfully",
                'leaveId': leave_id,
                'employeeId': leave_request.get('employeeId'),
                'employeeName': leave_request.get('employeeName', 'Unknown'),
                'leaveType': leave_request.get('leaveType'),
                'startDate': leave_request.get('startDate'),
                'endDate': leave_request.get('endDate'),
                'status': leave_request.get('status'),
                'duration': leave_request.get('duration'),
                'appliedAt': leave_request.get('appliedAt')
            }
        
        elif employee_id is not None:
            # Query all leave requests for this employee
            scan_response = table.scan(
                FilterExpression=Key('type').eq('LEAVE_REQUEST') & Key('employeeId').eq(employee_id)
            )
            
            leaves = scan_response.get('Items', [])
            
            if not leaves:
                return {
                    'success': True,
                    'message': f"No leave requests found for employee ID {employee_id}",
                    'employeeId': employee_id,
                    'leaveRequests': []
                }
            
            # Sort by applied date (newest first)
            leaves.sort(key=lambda x: x.get('appliedAt', ''), reverse=True)
            
            return {
                'success': True,
                'message': f"Found {len(leaves)} leave requests for employee ID {employee_id}",
                'employeeId': employee_id,
                'leaveRequests': leaves
            }
        
        else:
            return {
                'success': False,
                'message': "Either employee_id or leave_id must be provided"
            }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error retrieving leave status: {str(e)}"
        }

def lambda_handler(event, context):
    """
    Lambda handler for leave application/cancellation/balance/status
    Args:
        event (dict): Event data from AWS Lambda
        context (LambdaContext): Context object from AWS Lambda
    Returns:
        dict: Response to be sent back to the caller
    """
    try:
        # Extract information from the event
        agent = event.get('agent')
        action_group = event.get('actionGroup')
        function = event.get('function')
        parameters = event.get('parameters', [])
        
        # Convert parameters to a dictionary for easier access
        param_dict = {param['name']: param['value'] for param in parameters}
        
        result = None
        
        # Process based on the function called
        if function == 'apply_leave':
            employee_id = int(param_dict.get('employee_id'))
            start_date = param_dict.get('start_date')
            end_date = param_dict.get('end_date')
            leave_type = param_dict.get('leave_type', 'Annual')  # Default to Annual if not specified
            result = apply_leave(employee_id, start_date, end_date, leave_type)
        elif function == 'cancel_leave':
            leave_id = param_dict.get('leave_id')
            employee_id = param_dict.get('employee_id')
            leave_type = param_dict.get('leave_type')
            start_date = param_dict.get('start_date')
            
            if leave_id:
                leave_id = int(leave_id)
            if employee_id:
                employee_id = int(employee_id)
                
            result = cancel_leave(leave_id=leave_id, employee_id=employee_id, 
                                 leave_type=leave_type, start_date=start_date)
        elif function == 'get_leave_balance':
            employee_id = int(param_dict.get('employee_id'))
            result = get_leave_balance(employee_id)
        elif function == 'get_leave_status':
            employee_id = param_dict.get('employee_id')
            leave_id = param_dict.get('leave_id')
            
            if employee_id:
                employee_id = int(employee_id)
            if leave_id:
                leave_id = int(leave_id)
                
            result = get_leave_status(employee_id, leave_id)
        else:
            result = {
                'success': False,
                'message': f"Unknown function: {function}"
            }
        
        # Format the response for Bedrock agent
        response_body = {
            'TEXT': {
                'body': json.dumps(result, cls=DecimalEncoder)
            }
        }
        
        function_response = {
            'actionGroup': action_group,
            'function': function,
            'functionResponse': {
                'responseBody': response_body
            }
        }
        
        # Include session attributes if they exist
        session_attributes = event.get('sessionAttributes', {})
        prompt_session_attributes = event.get('promptSessionAttributes', {})
        
        action_response = {
            'messageVersion': '1.0',
            'response': function_response,
            'sessionAttributes': session_attributes,
            'promptSessionAttributes': prompt_session_attributes
        }
        
        return action_response
    
    except Exception as e:
        # Handle any unexpected errors
        error_response = {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', ''),
                'function': event.get('function', ''),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({
                                'success': False,
                                'message': f"Error processing request: {str(e)}"
                            }, cls=DecimalEncoder)
                        }
                    }
                }
            },
            'sessionAttributes': event.get('sessionAttributes', {}),
            'promptSessionAttributes': event.get('promptSessionAttributes', {})
        }
        
        return error_response