import boto3
import json
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from tabulate import tabulate
from dotenv import load_dotenv
import pathlib

# Load environment variables from .env file
env_path = pathlib.Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get email addresses from environment variables
EMPLOYEE_EMAIL = os.environ.get('EMPLOYEE_EMAIL', 'example@example.com')
APPROVER_EMAIL = os.environ.get('APPROVER_EMAIL', 'example@example.com')

def query_employee_leaves(table_name, employee_id, region='us-east-1'):
    """
    Query all leave requests for a specific employee
    
    Args:
        table_name (str): Name of the DynamoDB table
        employee_id (int): ID of the employee
        region (str): AWS region
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # First, verify the employee exists
    response = table.get_item(
        Key={
            'id': employee_id,
            'type': 'EMPLOYEE'
        }
    )
    
    if 'Item' not in response:
        print(f"Employee with ID {employee_id} not found")
        return
    
    employee = response['Item']
    print(f"Employee: {employee['name']} (ID: {employee_id})")
    print(f"Department: {employee.get('department', 'N/A')}")
    print(f"Email: {employee.get('email', 'N/A')}")
    
    # Display leave balances by type if available
    if 'leaveBalances' in employee:
        print("\nLeave Balances:")
        balance_data = []
        for leave_type, balance in employee['leaveBalances'].items():
            balance_data.append([leave_type, f"{balance} days"])
        print(tabulate(balance_data, headers=["Leave Type", "Balance"], tablefmt="simple"))
    else:
        print(f"Leave Balance: {employee.get('leaveBalance', 0)} days")
    
    print("\nLeave Requests:")
    
    # Query all leave requests for this employee
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST') & Key('employeeId').eq(employee_id)
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print("No leave requests found")
        return
    
    # Sort by applied date
    leaves.sort(key=lambda x: x.get('appliedAt', ''), reverse=True)
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        status_info = [leave['status']]
        if leave['status'] == 'APPROVED':
            status_info.append(f" ({leave.get('approvedAt', 'N/A')})")
        elif leave['status'] == 'REJECTED':
            status_info.append(f" ({leave.get('rejectedAt', 'N/A')})")
        elif leave['status'] == 'CANCELLED':
            status_info.append(f" ({leave.get('cancelledAt', 'N/A')})")
            
        notification_status = "Sent" if "notificationSent" in leave else "Not sent"
        
        table_data.append([
            str(leave['id']),
            ''.join(status_info),
            leave.get('leaveType', 'Not specified'),
            f"{leave['startDate']} to {leave['endDate']}",
            leave.get('appliedAt', 'N/A'),
            notification_status
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Status", "Type", "Period", "Applied At", "Notification"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def query_pending_leaves(table_name, region='us-east-1'):
    """
    Query all pending leave requests
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Scan the table for pending leave requests
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST') & Key('status').eq('PENDING')
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print("No pending leave requests found")
        return
    
    # Sort by applied date
    leaves.sort(key=lambda x: x.get('appliedAt', ''))
    
    print(f"Found {len(leaves)} pending leave requests:")
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        table_data.append([
            str(leave['id']),  # Convert ID to string to prevent scientific notation
            leave.get('employeeName', 'Unknown'),
            leave.get('employeeId', 'N/A'),  # Added employee ID to display
            leave.get('leaveType', 'Not specified'),
            f"{leave['startDate']} to {leave['endDate']}",
            leave.get('appliedAt', 'N/A')
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Employee", "Employee ID", "Type", "Period", "Applied At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def list_employees(table_name, region='us-east-1'):
    """
    List all employees
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Scan the table for employees
    scan_response = table.scan(
        FilterExpression=Key('type').eq('EMPLOYEE')
    )
    
    employees = scan_response.get('Items', [])
    
    if not employees:
        print("No employees found")
        return None
    
    # Sort by employee ID
    employees.sort(key=lambda x: x.get('id', 0))
    
    print(f"Found {len(employees)} employees:")
    
    # Print employees
    for i, employee in enumerate(employees, 1):
        print(f"{i}. {employee['name']} (ID: {employee['id']}) - {employee.get('department', 'N/A')}")
    
    return employees

def get_leave_types(table_name=None, region=None):
    """
    Get all leave types available in the system based on OCTANK INC Leave Policy
    
    Args:
        table_name (str, optional): Name of the DynamoDB table (not used, kept for compatibility)
        region (str, optional): AWS region (not used, kept for compatibility)
        
    Returns:
        list: List of leave types defined in OCTANK INC Leave Policy
    """
    # Static list of leave types based on OCTANK INC Leave Policy
    leave_types = [
        "Annual",
        "Sick",
        "Maternity",
        "Paternity",
        "Casual",
        "Bereavement",
        "Marriage",
        "WFH"
    ]
    
    return leave_types

def query_leave_balance(table_name, employee_id=None, employee_name=None, leave_type=None, region='us-east-1'):
    """
    Query leave balance for a specific employee by ID or name, optionally filtered by leave type
    
    Args:
        table_name (str): Name of the DynamoDB table
        employee_id (int, optional): ID of the employee
        employee_name (str, optional): Name of the employee (partial match)
        leave_type (str, optional): Type of leave to filter by
        region (str): AWS region
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Scan for employees
    scan_response = table.scan(
        FilterExpression=Key('type').eq('EMPLOYEE')
    )
    
    employees = scan_response.get('Items', [])
    
    if not employees:
        print("No employees found")
        return
    
    # Filter employees by ID or name if provided
    if employee_id is not None:
        employees = [e for e in employees if e['id'] == employee_id]
    elif employee_name is not None:
        employees = [e for e in employees if employee_name.lower() in e['name'].lower()]
    
    if not employees:
        print(f"No employees found matching the criteria")
        return
    
    # Display leave balances for each matching employee
    for employee in employees:
        print(f"\nEmployee: {employee['name']} (ID: {employee['id']})")
        print(f"Department: {employee.get('department', 'N/A')}")
        
        if 'leaveBalances' in employee:
            print("Leave Balances:")
            
            # Prepare data for tabular display
            balance_data = []
            
            # Filter by leave type if provided
            if leave_type:
                if leave_type in employee['leaveBalances']:
                    balance_data.append([leave_type, f"{employee['leaveBalances'][leave_type]} days"])
                else:
                    balance_data.append([leave_type, "Not available"])
            else:
                # Show all leave balances
                for lt, balance in employee['leaveBalances'].items():
                    balance_data.append([lt, f"{balance} days"])
            
            print(tabulate(balance_data, headers=["Leave Type", "Balance"], tablefmt="simple"))
        else:
            print(f"Leave Balance: {employee.get('leaveBalance', 0)} days")

def get_all_leaves(table_name, region='us-east-1'):
    """
    Get all leave requests in the system
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
        
    Returns:
        list: List of leave request items
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Query all leave requests
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST')
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print("No leave requests found")
        return []
    
    # Sort by applied date
    leaves.sort(key=lambda x: x.get('appliedAt', ''), reverse=True)
    
    print(f"Found {len(leaves)} leave requests:")
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        table_data.append([
            str(leave['id']),
            leave.get('employeeName', 'Unknown'),
            leave['status'],
            leave.get('leaveType', 'Not specified'),
            f"{leave['startDate']} to {leave['endDate']}",
            leave.get('appliedAt', 'N/A')
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Employee", "Status", "Type", "Period", "Applied At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    return leaves

def get_leaves_by_type(table_name, leave_type, region='us-east-1'):
    """
    Get leave requests filtered by leave type
    
    Args:
        table_name (str): Name of the DynamoDB table
        leave_type (str): Type of leave to filter by
        region (str): AWS region
        
    Returns:
        list: List of filtered leave request items
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Query leave requests by type
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST') & Attr('leaveType').eq(leave_type)
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print(f"No leave requests found for type: {leave_type}")
        return []
    
    # Sort by applied date
    leaves.sort(key=lambda x: x.get('appliedAt', ''), reverse=True)
    
    print(f"Found {len(leaves)} {leave_type} leave requests:")
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        table_data.append([
            str(leave['id']),
            leave.get('employeeName', 'Unknown'),
            leave['status'],
            f"{leave['startDate']} to {leave['endDate']}",
            leave.get('appliedAt', 'N/A')
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Employee", "Status", "Period", "Applied At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    return leaves

def get_approved_leaves(table_name, region='us-east-1'):
    """
    Get all approved leave requests
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
        
    Returns:
        list: List of approved leave request items
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Query approved leave requests
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST') & Key('status').eq('APPROVED')
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print("No approved leave requests found")
        return []
    
    # Sort by approved date if available, otherwise by applied date
    leaves.sort(key=lambda x: x.get('approvedAt', x.get('appliedAt', '')), reverse=True)
    
    print(f"Found {len(leaves)} approved leave requests:")
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        table_data.append([
            str(leave['id']),
            leave.get('employeeName', 'Unknown'),
            leave.get('leaveType', 'Not specified'),
            f"{leave['startDate']} to {leave['endDate']}",
            leave.get('appliedAt', 'N/A'),
            leave.get('approvedAt', 'N/A')
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Employee", "Type", "Period", "Applied At", "Approved At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    return leaves

def get_notification_status(table_name, region='us-east-1'):
    """
    Get notification status for all leave requests
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    # Scan the table for leave requests
    scan_response = table.scan(
        FilterExpression=Key('type').eq('LEAVE_REQUEST')
    )
    
    leaves = scan_response.get('Items', [])
    
    if not leaves:
        print("No leave requests found")
        return
    
    # Sort by notification status (not sent first)
    leaves.sort(key=lambda x: "notificationSent" in x)
    
    print(f"Found {len(leaves)} leave requests:")
    
    # Prepare data for tabular display
    table_data = []
    for leave in leaves:
        notification_status = "Sent" if "notificationSent" in leave else "Not sent"
        notification_time = leave.get("notificationSent", "N/A")
        
        table_data.append([
            str(leave['id']),
            leave.get('employeeName', 'Unknown'),
            leave['status'],
            leave.get('leaveType', 'Not specified'),
            f"{leave['startDate']} to {leave['endDate']}",
            notification_status,
            notification_time if notification_status == "Sent" else "N/A"
        ])
    
    # Print in tabular format
    headers = ["Leave ID", "Employee", "Status", "Type", "Period", "Notification", "Sent At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def interactive_menu(table_name, region='us-east-1'):
    """
    Interactive menu for querying leave requests
    
    Args:
        table_name (str): Name of the DynamoDB table
        region (str): AWS region
    """
    while True:
        print("\n===== Leave Management System =====")
        print("1. Query leaves for a specific employee")
        print("2. Query all pending leave requests")
        print("3. Query leave balances")
        print("4. Get all leave requests")
        print("5. Get leaves by type")
        print("6. Get approved leaves")
        print("7. Get notification status")
        print("8. Exit")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            employees = list_employees(table_name, region)
            if employees:
                try:
                    emp_input = input("\nEnter employee number or ID (or 0 to go back): ")
                    if emp_input == '0':
                        continue
                    
                    # Try to parse as employee number (index in the list)
                    try:
                        emp_choice = int(emp_input)
                        if 1 <= emp_choice <= len(employees):
                            employee_id = employees[emp_choice-1]['id']
                            query_employee_leaves(table_name, employee_id, region)
                        else:
                            # If not a valid index, try as an employee ID
                            employee_id = int(emp_input)
                            # Check if this ID exists in the employees list
                            if any(e['id'] == employee_id for e in employees):
                                query_employee_leaves(table_name, employee_id, region)
                            else:
                                print(f"Employee with ID {employee_id} not found")
                    except ValueError:
                        print("Please enter a valid number")
                except Exception as e:
                    print(f"Error: {str(e)}")
        elif choice == '2':
            query_pending_leaves(table_name, region)
        elif choice == '3':
            print("\n1. Query by employee ID")
            print("2. Query by employee name")
            print("3. Query all employees")
            
            sub_choice = input("\nEnter your choice (1-3): ")
            
            if sub_choice == '1':
                try:
                    emp_id = int(input("Enter employee ID: "))
                    leave_type = input("Enter leave type (or press Enter for all): ").strip() or None
                    query_leave_balance(table_name, employee_id=emp_id, leave_type=leave_type, region=region)
                except ValueError:
                    print("Please enter a valid employee ID")
            elif sub_choice == '2':
                emp_name = input("Enter employee name (partial match): ")
                leave_type = input("Enter leave type (or press Enter for all): ").strip() or None
                query_leave_balance(table_name, employee_name=emp_name, leave_type=leave_type, region=region)
            elif sub_choice == '3':
                # Get all leave types from the system
                leave_types = get_leave_types(table_name, region)
                
                if not leave_types:
                    print("No leave types found in the system")
                    continue
                
                print("\nAvailable leave types:")
                for i, lt in enumerate(leave_types, 1):
                    print(f"{i}. {lt}")
                print(f"{len(leave_types) + 1}. All types")
                
                try:
                    type_choice = int(input(f"\nSelect leave type (1-{len(leave_types) + 1}): "))
                    if 1 <= type_choice <= len(leave_types):
                        leave_type = leave_types[type_choice - 1]
                    elif type_choice == len(leave_types) + 1:
                        leave_type = None
                    else:
                        print("Invalid choice")
                        continue
                except ValueError:
                    print("Please enter a valid number")
                    continue
                
                query_leave_balance(table_name, leave_type=leave_type, region=region)
            else:
                print("Invalid choice")
        elif choice == '4':
            get_all_leaves(table_name, region)
        elif choice == '5':
            # Get all leave types from the system
            leave_types = get_leave_types(table_name, region)
            
            if not leave_types:
                print("No leave types found in the system")
                continue
            
            print("\nAvailable leave types:")
            for i, lt in enumerate(leave_types, 1):
                print(f"{i}. {lt}")
            
            try:
                type_choice = int(input(f"\nSelect leave type (1-{len(leave_types)}): "))
                if 1 <= type_choice <= len(leave_types):
                    leave_type = leave_types[type_choice - 1]
                    get_leaves_by_type(table_name, leave_type, region)
                else:
                    print("Invalid choice")
            except ValueError:
                print("Please enter a valid number")
        elif choice == '6':
            get_approved_leaves(table_name, region)
        elif choice == '7':
            get_notification_status(table_name, region)
        elif choice == '8':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

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

if __name__ == "__main__":
    table_name = get_table_name()
    region = os.environ.get('AWS_REGION', 'us-west-2')
    
    print(f"Connecting to table: {table_name} in region: {region}")
    interactive_menu(table_name, region)