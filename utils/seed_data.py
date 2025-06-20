import boto3
import json
import os
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import pathlib

# Load environment variables from .env file
env_path = pathlib.Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get email addresses from environment variables
EMPLOYEE_EMAIL = os.environ.get('EMPLOYEE_EMAIL', 'employee@example.com')
APPROVER_EMAIL = os.environ.get('APPROVER_EMAIL', 'approver@example.com')

# Leave types as per OCTANK INC Leave Policy 2025
LEAVE_TYPES = [
    {"type": "Annual", "balance": 20},
    {"type": "Sick", "balance": 12},
    {"type": "Maternity", "balance": 26 * 5},  # 26 weeks converted to days
    {"type": "Paternity", "balance": 4 * 5},    # 4 weeks converted to days
    {"type": "Casual", "balance": 6},
    {"type": "Bereavement", "balance": 5},
    {"type": "Marriage", "balance": 5},
    {"type": "WFH", "balance": 24}              # 2 days per month * 12 months
]

# Sample employee data with email addresses
SAMPLE_EMPLOYEES = [
    {"id": 1001, "name": "John Doe", "email": EMPLOYEE_EMAIL, "department": "Engineering"},
    {"id": 1002, "name": "Jane Smith", "email": EMPLOYEE_EMAIL, "department": "HR"},
    {"id": 1003, "name": "Michael Johnson", "email": EMPLOYEE_EMAIL, "department": "Finance"},
    {"id": 1004, "name": "Emily Davis", "email": EMPLOYEE_EMAIL, "department": "Marketing"},
    {"id": 1005, "name": "Robert Wilson", "email": EMPLOYEE_EMAIL, "department": "Engineering"}
]

# Sample leave requests
def generate_leave_requests(num_requests=10):
    leave_requests = []
    statuses = ["PENDING", "APPROVED", "REJECTED", "CANCELLED"]
    
    for i in range(num_requests):
        employee = random.choice(SAMPLE_EMPLOYEES)
        employee_id = employee["id"]
        
        # Generate random dates
        # Import timezone from datetime to create aware datetime objects
        from datetime import timezone
        start_date = datetime.now(timezone.utc) + timedelta(days=random.randint(1, 30))
        end_date = start_date + timedelta(days=random.randint(1, 7))
        
        # Format dates as strings
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Calculate duration in days
        duration = (end_date - start_date).days + 1
        
        # Generate a unique leave ID
        leave_id = int(f"{employee_id}{i+1}")
        
        # Randomly select a status and leave type
        status = random.choice(statuses)
        leave_type_obj = random.choice(LEAVE_TYPES)
        leave_type = leave_type_obj["type"]
        
        leave_request = {
            "id": leave_id,
            "type": "LEAVE_REQUEST",
            "employeeId": employee_id,
            "employeeName": employee["name"],
            "employeeEmail": employee["email"],
            "startDate": start_date_str,
            "endDate": end_date_str,
            "leaveType": leave_type,
            "duration": duration,
            "status": status,
            "appliedAt": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10))).isoformat()
        }
        
        # Add additional fields based on status
        if status == "APPROVED":
            leave_request["approvedAt"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5))).isoformat()
            leave_request["approverEmail"] = APPROVER_EMAIL
            # Add notification status for some approved leaves
            if random.choice([True, False]):
                leave_request["notificationSent"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 3))).isoformat()
        elif status == "REJECTED":
            leave_request["rejectedAt"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5))).isoformat()
            leave_request["rejectionReason"] = random.choice(["Insufficient leave balance", "Critical project deadline", "Team member already on leave"])
            leave_request["approverEmail"] = APPROVER_EMAIL
            # Add notification status for some rejected leaves
            if random.choice([True, False]):
                leave_request["notificationSent"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 3))).isoformat()
        elif status == "CANCELLED":
            leave_request["cancelledAt"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 3))).isoformat()
        
        leave_requests.append(leave_request)
    
    return leave_requests

def get_table_name():
    """Get the DynamoDB table name from CloudFormation outputs"""
    try:
        # Try to get table name from environment variable first (for Lambda execution)
        if 'TABLE_NAME' in os.environ:
            return os.environ['TABLE_NAME']
        
        # Otherwise, look up the table name from CloudFormation outputs
        region = os.environ.get('AWS_REGION', 'us-west-2')
        cfn = boto3.client('cloudformation', region_name=region)
        stacks = cfn.list_stacks(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE'])
        
        # Find the LMS stack
        stack_name = None
        for stack in stacks['StackSummaries']:
            if 'LmsCdkStack' in stack['StackName']:
                stack_name = stack['StackName']
                break
        
        if not stack_name:
            # Try with a default name if we couldn't find it
            stack_name = 'LmsCdkStack'
        
        # Get the outputs from the stack
        response = cfn.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        # Find the table name output
        for output in outputs:
            if output['OutputKey'] == 'LeaveTableName':
                return output['OutputValue']
        
        # If we couldn't find it, use a default name
        return 'LeaveManagementTable'
    
    except Exception as e:
        print(f"Error getting table name: {str(e)}")
        return 'LeaveManagementTable'  # Default fallback

def delete_all_data(table_name, region='us-west-2'):
    """Delete all data from the DynamoDB table"""
    print(f"Deleting all data from table: {table_name} in region: {region}")
    
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Scan all items in the table
    response = table.scan()
    items = response.get('Items', [])
    
    # Delete each item
    count = 0
    for item in items:
        table.delete_item(
            Key={
                'id': item['id'],
                'type': item['type']
            }
        )
        count += 1
    
    print(f"Deleted {count} items from the table")
    return count

def seed_data():
    """Seed the DynamoDB table with sample data"""
    # Get the table name from CloudFormation outputs
    table_name = get_table_name()
    region = os.environ.get('AWS_REGION', 'us-west-2')
    
    # Delete existing data
    delete_all_data(table_name, region)
    
    print(f"Seeding data to table: {table_name} in region: {region}")
    
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Add employees with leave balances
    for employee in SAMPLE_EMPLOYEES:
        employee_item = employee.copy()
        employee_item["type"] = "EMPLOYEE"
        
        # Add leave balances for each leave type
        employee_item["leaveBalances"] = {}
        for leave_type in LEAVE_TYPES:
            employee_item["leaveBalances"][leave_type["type"]] = leave_type["balance"]
        
        print(f"Adding employee: {employee_item['name']}")
        table.put_item(Item=employee_item)
    
    # Add leave types
    for i, leave_type in enumerate(LEAVE_TYPES):
        leave_type_item = leave_type.copy()
        leave_type_item["id"] = 5000 + i
        leave_type_item["type"] = "LEAVE_TYPE"
        
        print(f"Adding leave type: {leave_type_item['type']}")
        table.put_item(Item=leave_type_item)
    
    # Add leave requests
    leave_requests = generate_leave_requests()
    for leave_request in leave_requests:
        print(f"Adding leave request: {leave_request['id']} for {leave_request['employeeName']}")
        table.put_item(Item=leave_request)
    
    print(f"Successfully seeded {len(SAMPLE_EMPLOYEES)} employees, {len(LEAVE_TYPES)} leave types, and {len(leave_requests)} leave requests")

if __name__ == "__main__":
    seed_data()