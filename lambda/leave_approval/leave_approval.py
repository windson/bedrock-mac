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

def approve_leave(leave_id):
    """
    Approve a leave request and update leave balance
    
    Args:
        leave_id (int): ID of the leave request to approve
        
    Returns:
        dict: Updated leave request details
    """
    try:
        # Get the leave request
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
        
        # Check if leave is already approved or rejected
        if leave_request['status'] != 'PENDING':
            return {
                'success': False,
                'message': f"Leave request is already {leave_request['status'].lower()}"
            }
        
        # Get the employee record to update leave balance
        employee_id = leave_request['employeeId']
        leave_type = leave_request['leaveType']
        duration = leave_request.get('duration', 1)  # Default to 1 day if duration not specified
        
        employee_response = table.get_item(
            Key={
                'id': employee_id,
                'type': 'EMPLOYEE'
            }
        )
        
        if 'Item' not in employee_response:
            return {
                'success': False,
                'message': f"Employee with ID {employee_id} not found"
            }
        
        employee = employee_response['Item']
        
        # Check if employee has sufficient leave balance
        if 'leaveBalances' not in employee or leave_type not in employee['leaveBalances']:
            return {
                'success': False,
                'message': f"Leave type {leave_type} not found in employee's leave balances"
            }
        
        current_balance = employee['leaveBalances'][leave_type]
        
        if current_balance < duration:
            return {
                'success': False,
                'message': f"Insufficient leave balance. Available: {current_balance}, Required: {duration}"
            }
        
        # Update the leave request status
        # Import datetime and timezone to create aware datetime objects
        from datetime import datetime, timezone
        # datetime.now(timezone.utc) creates an aware datetime object in UTC
        table.update_item(
            Key={
                'id': leave_id,
                'type': 'LEAVE_REQUEST'
            },
            UpdateExpression="SET #status = :status, approvedAt = :approvedAt",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'APPROVED',
                ':approvedAt': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Update the employee's leave balance
        new_balance = current_balance - duration
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
            'message': f"Leave request with ID {leave_id} has been approved. Updated {leave_type} leave balance: {new_balance}",
            'leaveId': leave_id,
            'leaveType': leave_type,
            'newBalance': new_balance
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error approving leave: {str(e)}"
        }

from datetime import datetime, timezone  # Import timezone to create aware datetime objects

def reject_leave(leave_id, reason=None):
    """
    Reject a leave request
    
    Args:
        leave_id (int): ID of the leave request to reject
        reason (str, optional): Reason for rejection
        
    Returns:
        dict: Updated leave request details
    """
    try:
        # Get the leave request
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
        
        # Check if leave is already approved or rejected
        if leave_request['status'] != 'PENDING':
            return {
                'success': False,
                'message': f"Leave request is already {leave_request['status'].lower()}"
            }
        
        update_expression = "SET #status = :status, rejectedAt = :rejectedAt"
        expression_values = {
            ':status': 'REJECTED',
            ':rejectedAt': datetime.now(timezone.utc).isoformat()  # Use aware datetime object
        }
        
        if reason:
            update_expression += ", rejectionReason = :reason"
            expression_values[':reason'] = reason
        
        # Update the leave request status
        table.update_item(
            Key={
                'id': leave_id,
                'type': 'LEAVE_REQUEST'
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues=expression_values
        )
        
        return {
            'success': True,
            'message': f"Leave request with ID {leave_id} has been rejected",
            'leaveId': leave_id,
            'reason': reason if reason else 'No reason provided'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error rejecting leave: {str(e)}"
        }

def get_pending_leave_requests(employee_id=None, limit=10):
    """
    Get pending leave requests for review
    
    Args:
        employee_id (int, optional): Filter by employee ID
        limit (int, optional): Maximum number of requests to return
        
    Returns:
        dict: List of pending leave requests
    """
    try:
        filter_expression = Key('type').eq('LEAVE_REQUEST') & Key('status').eq('PENDING')
        
        # If employee_id is provided, filter by that employee
        if employee_id is not None:
            scan_response = table.scan(
                FilterExpression=filter_expression & Key('employeeId').eq(employee_id)
            )
        else:
            scan_response = table.scan(
                FilterExpression=filter_expression
            )
        
        leaves = scan_response.get('Items', [])
        
        # Sort by applied date (oldest first to prioritize them)
        leaves.sort(key=lambda x: x.get('appliedAt', ''))
        
        # Limit the number of results
        leaves = leaves[:limit]
        
        if not leaves:
            return {
                'success': True,
                'message': "No pending leave requests found",
                'requests': []
            }
        
        return {
            'success': True,
            'message': f"Found {len(leaves)} pending leave requests",
            'requests': leaves
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error retrieving pending leave requests: {str(e)}"
        }

def lambda_handler(event, context):
    """
    Lambda handler for leave approval/rejection
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
        if function == 'approve_leave':
            leave_id = int(param_dict.get('leave_id'))
            result = approve_leave(leave_id)
        elif function == 'reject_leave':
            leave_id = int(param_dict.get('leave_id'))
            reason = param_dict.get('reason')
            result = reject_leave(leave_id, reason)
        elif function == 'get_pending_leave_requests':
            employee_id = param_dict.get('employee_id')
            limit = param_dict.get('limit', 10)
            
            if employee_id:
                employee_id = int(employee_id)
            if limit:
                limit = int(limit)
                
            result = get_pending_leave_requests(employee_id, limit)
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