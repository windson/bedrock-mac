# # Multi Agents Collaboration using Amazon Bedrock Agents

## Leave Management System - AWS CDK Project

This project implements a Leave Management System using AWS CDK, Lambda, and DynamoDB. It's designed to be used with Amazon Bedrock Agents.

## Architecture

The project consists of:

1. **DynamoDB Table**: Stores employee and leave request data
2. **Lambda Functions**:
   - **Leave Approval Lambda**: Handles approving and rejecting leave requests
   - **Leave Application Lambda**: Handles applying for and cancelling leave requests
   - **Leave Notification Lambda**: Handles sending notifications to approvers and employees
3. **SNS Topic**: For sending email notifications
4. **Utility Scripts**: For seeding data and querying the DynamoDB table

## Lambda Functions

### Leave Approval Lambda

This Lambda function provides the following operations:
- `approve_leave`: Approves a pending leave request
- `reject_leave`: Rejects a pending leave request with an optional reason
- `get_pending_leave_requests`: Retrieves a list of pending leave requests for review

### Leave Application Lambda

This Lambda function provides the following operations:
- `apply_leave`: Creates a new leave request for an employee with leave type
- `cancel_leave`: Cancels an existing leave request
- `get_leave_balance`: Retrieves leave balances for an employee
- `get_leave_status`: Gets status information for leave requests

### Leave Notification Lambda

This Lambda function provides the following operations:
- `notify_leave_request`: Sends notifications about a leave request to both approver and employee
- `get_notification_status`: Gets notification status for a leave request
- `resend_notification`: Resends notifications for a leave request

## Deployment

To deploy this project:

1. Install dependencies:
   ```
   npm install
   ```

2. Build the project:
   ```
   npm run build
   ```

3. Deploy the stack:
   ```
   npx cdk deploy
   ```

## Using the Utility Scripts

The utility scripts require boto3 to interact with AWS services. You can run them using Docker to avoid installing dependencies directly on your system.

### Option 1: Using a Virtual Environment

If you prefer not to use Docker, you can create a temporary virtual environment:

```bash
# Create a virtual environment
python -m venv lms_venv

# Activate the virtual environment
# On Windows:
# lms_venv\Scripts\activate
# On macOS/Linux:
source lms_venv/bin/activate

# Install dependencies
pip install -r lms_cdk/utils/requirements.txt

# Run the seed data script
python lms_cdk/utils/seed_data.py

# Run the query tool
python lms_cdk/utils/query_leaves.py

# Deactivate the virtual environment when done
deactivate
```

### Option 2: Using Docker

1. Build a Docker image with the required dependencies:

```bash
# Create a Dockerfile in the project root
cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app
COPY lms_cdk/utils /app/utils
RUN pip install boto3==1.28.38 botocore==1.31.38

# Set AWS credentials as environment variables if needed
# ENV AWS_ACCESS_KEY_ID=your_access_key
# ENV AWS_SECRET_ACCESS_KEY=your_secret_key
# ENV AWS_REGION=us-west-2

WORKDIR /app/utils
EOF

# Build the Docker image
docker build -t lms-utils .
```

2. Run the seed data script:

```bash
# Make sure to set your AWS credentials if not using IAM roles
docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_REGION lms-utils python seed_data.py
```

3. Run the query tool:

```bash
# Interactive mode requires the -it flags
docker run -it -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_REGION lms-utils python query_leaves.py
```


### Option 3: Using AWS CloudShell

You can also run these scripts directly in AWS CloudShell, which already has boto3 installed:

1. Upload the utility scripts to CloudShell
2. Run the scripts:

```bash
python seed_data.py
python query_leaves.py
```

## Utility Scripts Features

### Seed Data Script

The `seed_data.py` script:
- Creates sample employees with appropriate leave balances
- Adds leave types according to OCTANK's leave policy
- Generates random leave requests with various statuses
- Automatically detects the DynamoDB table from CloudFormation outputs

### Query Tool

The `query_leaves.py` interactive tool allows you to:
1. Query leaves for a specific employee (with employee selection)
2. Query all pending leave requests
3. Query leave balances
   - By employee ID
   - By employee name
   - For all employees
   - Filter by leave type
4. Exit

## Running Utility Scripts with a Helper Script

For convenience, a helper script is provided to run the utility scripts using Docker:

```bash
# Make the script executable
chmod +x run_utils.sh

# Run the script
./run_utils.sh
```

The script will:
1. Build a Docker image with the required dependencies
2. Present a menu to choose which utility to run
3. Run the selected utility in a Docker container

## Integrating with Amazon Bedrock Agents

To integrate these Lambda functions with Amazon Bedrock Agents:

1. Create an agent in the Amazon Bedrock console
2. Create three action groups:
   - **Leave Approval**: With functions `approve_leave`, `reject_leave`, and `get_pending_leave_requests`
   - **Leave Application**: With functions `apply_leave`, `cancel_leave`, `get_leave_balance`, and `get_leave_status`
   - **Leave Notification**: With functions `notify_leave_request`, `get_notification_status`, and `resend_notification`
3. Configure each action group to use the corresponding Lambda function
4. Add the necessary IAM permissions to allow Bedrock to invoke the Lambda functions

## Environment Variables

The project uses environment variables loaded from `.env` files:

1. **Main `.env` file** (in project root):
   - `EMPLOYEE_EMAIL`: Email address for employees (default: none)
   - `APPROVER_EMAIL`: Email address for approvers (default: none)

2. **Lambda-specific `.env` files** (in each Lambda directory):
   - Used for local development and testing

3. **Utility-specific `.env` file** (in utils directory):
   - Used by utility scripts for seeding data and querying

The Lambda functions also use these environment variables set by CDK:
- `TABLE_NAME`: Name of the DynamoDB table
- `SNS_TOPIC_ARN`: ARN of the SNS topic for notifications

## Function Schemas

### Leave Approval Lambda

#### approve_leave
```json
{
  "name": "approve_leave",
  "description": "Approve a pending leave request",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to approve",
      "required": true
    }
  ]
}
```

#### reject_leave
```json
{
  "name": "reject_leave",
  "description": "Reject a pending leave request",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to reject",
      "required": true
    },
    {
      "name": "reason",
      "type": "string",
      "description": "Reason for rejecting the leave request",
      "required": false
    }
  ]
}
```

#### get_pending_leave_requests
```json
{
  "name": "get_pending_leave_requests",
  "description": "Get a list of pending leave requests for review",
  "parameters": [
    {
      "name": "employee_id",
      "type": "integer",
      "description": "Optional ID of the employee to filter requests by",
      "required": false
    },
    {
      "name": "limit",
      "type": "integer",
      "description": "Maximum number of requests to return (default: 10)",
      "required": false
    }
  ]
}
```

### Leave Application Lambda

#### apply_leave
```json
{
  "name": "apply_leave",
  "description": "Apply for a new leave",
  "parameters": [
    {
      "name": "employee_id",
      "type": "integer",
      "description": "ID of the employee applying for leave",
      "required": true
    },
    {
      "name": "start_date",
      "type": "string",
      "description": "Start date of the leave (YYYY-MM-DD)",
      "required": true
    },
    {
      "name": "end_date",
      "type": "string",
      "description": "End date of the leave (YYYY-MM-DD)",
      "required": true
    },
    {
      "name": "leave_type",
      "type": "string",
      "description": "Type of leave (e.g., Annual, Sick, Personal)",
      "required": true
    }
  ]
}
```

#### cancel_leave
```json
{
  "name": "cancel_leave",
  "description": "Cancel an existing leave request",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to cancel",
      "required": true
    }
  ]
}
```

#### get_leave_balance
```json
{
  "name": "get_leave_balance",
  "description": "Get leave balance for an employee",
  "parameters": [
    {
      "name": "employee_id",
      "type": "integer",
      "description": "ID of the employee",
      "required": true
    }
  ]
}
```

#### get_leave_status
```json
{
  "name": "get_leave_status",
  "description": "Get leave status for an employee or a specific leave request",
  "parameters": [
    {
      "name": "employee_id",
      "type": "integer",
      "description": "ID of the employee (optional if leave_id is provided)",
      "required": false
    },
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the specific leave request (optional if employee_id is provided)",
      "required": false
    }
  ]
}
```

### Leave Notification Lambda

#### notify_leave_request
```json
{
  "name": "notify_leave_request",
  "description": "Send notifications about a leave request to both approver and employee",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to send notifications for",
      "required": true
    }
  ]
}
```

#### get_notification_status
```json
{
  "name": "get_notification_status",
  "description": "Get notification status for a leave request",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to check notification status",
      "required": true
    }
  ]
}
```

#### resend_notification
```json
{
  "name": "resend_notification",
  "description": "Resend notifications for a leave request",
  "parameters": [
    {
      "name": "leave_id",
      "type": "integer",
      "description": "ID of the leave request to resend notifications for",
      "required": true
    }
  ]
}
```