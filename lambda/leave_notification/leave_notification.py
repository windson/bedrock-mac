import json
import boto3
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Custom JSON encoder to handle Decimal objects
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'LeaveManagementTable'))

# Initialize SNS client
sns = boto3.client('sns')

# Get email addresses from environment variables configured in Lambda
EMPLOYEE_EMAIL = os.environ.get('EMPLOYEE_EMAIL')
APPROVER_EMAIL = os.environ.get('APPROVER_EMAIL')

def notify_leave_request(leave_id):
    """
    Notify both approver and employee about a leave request
    
    Args:
        leave_id (int): ID of the leave request
        
    Returns:
        dict: Notification status
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
        employee_id = leave_request['employeeId']
        
        # Get the employee details
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
        employee_name = employee.get('name', 'Unknown')
        
        # Prepare notification message
        leave_type = leave_request.get('leaveType', 'Not specified')
        start_date = leave_request.get('startDate', 'Not specified')
        end_date = leave_request.get('endDate', 'Not specified')
        status = leave_request.get('status', 'PENDING')
        
        # Create message based on leave status
        if status == 'PENDING':
            subject = f"New Leave Request: {employee_name} ({leave_id})"
            approver_message = f"""
New Leave Request Notification:

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: PENDING APPROVAL
Leave ID: {leave_id}

Please review this leave request at your earliest convenience.
            """
            
            employee_message = f"""
Leave Request Confirmation:

Your leave request has been submitted and is pending approval.

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: PENDING APPROVAL
Leave ID: {leave_id}

You will be notified when your request is approved or rejected.
            """
        elif status == 'APPROVED':
            subject = f"Leave Request Approved: {employee_name} ({leave_id})"
            approver_message = f"""
Leave Request Approved Confirmation:

You have approved the following leave request:

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: APPROVED
Leave ID: {leave_id}
Approved At: {leave_request.get('approvedAt', 'Not specified')}
            """
            
            employee_message = f"""
Leave Request Approved:

Your leave request has been approved.

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: APPROVED
Leave ID: {leave_id}
Approved At: {leave_request.get('approvedAt', 'Not specified')}
            """
        elif status == 'REJECTED':
            subject = f"Leave Request Rejected: {employee_name} ({leave_id})"
            rejection_reason = leave_request.get('rejectionReason', 'No reason provided')
            
            approver_message = f"""
Leave Request Rejection Confirmation:

You have rejected the following leave request:

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: REJECTED
Leave ID: {leave_id}
Rejected At: {leave_request.get('rejectedAt', 'Not specified')}
Reason: {rejection_reason}
            """
            
            employee_message = f"""
Leave Request Rejected:

Your leave request has been rejected.

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: REJECTED
Leave ID: {leave_id}
Rejected At: {leave_request.get('rejectedAt', 'Not specified')}
Reason: {rejection_reason}
            """
        elif status == 'CANCELLED':
            subject = f"Leave Request Cancelled: {employee_name} ({leave_id})"
            
            approver_message = f"""
Leave Request Cancellation Notification:

The following leave request has been cancelled:

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: CANCELLED
Leave ID: {leave_id}
Cancelled At: {leave_request.get('cancelledAt', 'Not specified')}
            """
            
            employee_message = f"""
Leave Request Cancellation Confirmation:

Your leave request has been cancelled.

Employee: {employee_name} (ID: {employee_id})
Leave Type: {leave_type}
Period: {start_date} to {end_date}
Status: CANCELLED
Leave ID: {leave_id}
Cancelled At: {leave_request.get('cancelledAt', 'Not specified')}
            """
        else:
            return {
                'success': False,
                'message': f"Unknown leave status: {status}"
            }
        
        # Send notifications via SNS
        # Use the pre-configured SNS topic and send emails directly
        try:
            # Get the SNS topic ARN from environment variables
            topic_arn = os.environ.get('SNS_TOPIC_ARN')
            
            # Send to approver using SES (via SNS)
            approver_response = sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps({
                    'default': 'Leave notification',
                    'email': approver_message
                }),
                Subject=subject,
                MessageStructure='json',
                MessageAttributes={
                    'email': {
                        'DataType': 'String',
                        'StringValue': APPROVER_EMAIL
                    }
                }
            )
            
            # Send to employee using SES (via SNS)
            employee_response = sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps({
                    'default': 'Leave notification',
                    'email': employee_message
                }),
                Subject=subject,
                MessageStructure='json',
                MessageAttributes={
                    'email': {
                        'DataType': 'String',
                        'StringValue': EMPLOYEE_EMAIL
                    }
                }
            )
            
            # Update the leave request to mark notifications as sent
            table.update_item(
                Key={
                    'id': leave_id,
                    'type': 'LEAVE_REQUEST'
                },
                UpdateExpression="SET notificationSent = :notificationSent",
                ExpressionAttributeValues={
                    ':notificationSent': datetime.now().isoformat()
                }
            )
            
            return {
                'success': True,
                'message': f"Notifications sent successfully for leave request {leave_id}",
                'approverEmail': APPROVER_EMAIL,
                'employeeEmail': EMPLOYEE_EMAIL,
                'status': status
            }
        
        except Exception as e:
            logger.error(f"Error sending notifications: {str(e)}")
            return {
                'success': False,
                'message': f"Error sending notifications: {str(e)}"
            }
    
    except Exception as e:
        logger.error(f"Error in notify_leave_request: {str(e)}")
        return {
            'success': False,
            'message': f"Error processing notification: {str(e)}"
        }

def get_notification_status(leave_id):
    """
    Get notification status for a leave request
    
    Args:
        leave_id (int): ID of the leave request
        
    Returns:
        dict: Notification status information
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
        
        notification_status = {
            'leaveId': leave_id,
            'status': leave_request.get('status', 'UNKNOWN'),
            'notificationSent': 'notificationSent' in leave_request,
            'sentAt': leave_request.get('notificationSent', 'Not sent')
        }
        
        return {
            'success': True,
            'message': f"Notification status retrieved for leave request {leave_id}",
            'notificationStatus': notification_status
        }
    
    except Exception as e:
        logger.error(f"Error in get_notification_status: {str(e)}")
        return {
            'success': False,
            'message': f"Error retrieving notification status: {str(e)}"
        }

def resend_notification(leave_id):
    """
    Resend notification for a leave request
    
    Args:
        leave_id (int): ID of the leave request
        
    Returns:
        dict: Notification status
    """
    try:
        # First check if the leave request exists
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
        
        # Simply call the notify function again
        result = notify_leave_request(leave_id)
        
        if result['success']:
            return {
                'success': True,
                'message': f"Notification resent successfully for leave request {leave_id}",
                'approverEmail': APPROVER_EMAIL,
                'employeeEmail': EMPLOYEE_EMAIL
            }
        else:
            return result
    
    except Exception as e:
        logger.error(f"Error in resend_notification: {str(e)}")
        return {
            'success': False,
            'message': f"Error resending notification: {str(e)}"
        }

def lambda_handler(event, context):
    """
    Lambda handler for leave notifications
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
        if function == 'notify_leave_request':
            leave_id = int(param_dict.get('leave_id'))
            result = notify_leave_request(leave_id)
        elif function == 'get_notification_status':
            leave_id = int(param_dict.get('leave_id'))
            result = get_notification_status(leave_id)
        elif function == 'resend_notification':
            leave_id = int(param_dict.get('leave_id'))
            result = resend_notification(leave_id)
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
        logger.error(f"Error in lambda_handler: {str(e)}")
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